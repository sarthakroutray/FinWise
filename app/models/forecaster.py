import os
import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import joblib
import keras
from sklearn.preprocessing import MinMaxScaler

from app.core.config import config


class LSTMForecaster:
    """LSTM-based time-series forecaster for daily spending prediction."""

    def __init__(
        self,
        lookback: int = config.LSTM_LOOKBACK,
        epochs: int = config.LSTM_EPOCHS,
    ) -> None:
        self.lookback = lookback
        self.epochs = epochs
        self.model: keras.Model | None = None
        self.scaler: MinMaxScaler = MinMaxScaler()
        self._model_path = Path(config.MODEL_DIR) / "lstm_forecaster.keras"
        self._scaler_path = Path(config.MODEL_DIR) / "lstm_scaler.pkl"
        self._logger = logging.getLogger(__name__)

    def _sanitize_series(self, series: pd.Series) -> pd.Series:
        """Return a finite float series with gaps filled for stable modeling."""
        cleaned = pd.to_numeric(series, errors="coerce")
        cleaned = cleaned.replace([np.inf, -np.inf], np.nan)
        cleaned = cleaned.ffill().bfill().fillna(0.0)
        return cleaned.astype("float32")

    def _baseline_forecast(self, series: pd.Series, horizon: int) -> np.ndarray:
        """Fallback forecast when model/scaler are unavailable or fail."""
        if horizon <= 0:
            return np.array([], dtype="float32")
        clean = self._sanitize_series(series)
        if clean.empty:
            return np.zeros(horizon, dtype="float32")
        baseline = float(clean.iloc[-1])
        return np.full(horizon, baseline, dtype="float32")

    def _seed_sequence(self, scaled: np.ndarray) -> np.ndarray:
        """Build a lookback-sized seed window for iterative prediction."""
        if len(scaled) >= self.lookback:
            seed = scaled[-self.lookback:]
        else:
            pad_value = float(scaled[0, 0]) if len(scaled) > 0 else 0.0
            pad = np.full((self.lookback - len(scaled), 1), pad_value, dtype=scaled.dtype)
            seed = np.vstack([pad, scaled])
        return seed.reshape(1, self.lookback, 1)

    def _build_model(self, input_shape: tuple) -> keras.Model:
        """Construct a 2-layer LSTM architecture."""
        model = keras.Sequential([
            keras.layers.LSTM(64, return_sequences=True, input_shape=input_shape),
            keras.layers.Dropout(0.2),
            keras.layers.LSTM(32, return_sequences=False),
            keras.layers.Dropout(0.2),
            keras.layers.Dense(1),
        ])
        model.compile(optimizer="adam", loss="mse")
        return model

    def _create_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create sliding window sequences from 1D array."""
        X, y = [], []
        for i in range(len(data) - self.lookback):
            X.append(data[i : i + self.lookback])
            y.append(data[i + self.lookback])
        return np.array(X), np.array(y)

    def fit(self, series: pd.Series) -> None:
        """Scale data, create sequences, train LSTM, save model + scaler."""
        clean = self._sanitize_series(series)
        if clean.empty:
            return
        values = clean.values.reshape(-1, 1)
        try:
            scaled = self.scaler.fit_transform(values)
            X, y = self._create_sequences(scaled)
            if len(X) == 0:
                # Not enough data for lookback window
                return
            X = X.reshape(X.shape[0], X.shape[1], 1)
            self.model = self._build_model((self.lookback, 1))
            self.model.fit(X, y, epochs=self.epochs, batch_size=16, verbose=0)
            os.makedirs(config.MODEL_DIR, exist_ok=True)
            self.model.save(self._model_path)
            joblib.dump(self.scaler, self._scaler_path)
        except Exception as e:
            self._logger.warning("LSTM training failed; using fallback forecasting. Error: %s", e)
            self.model = None

    def load(self) -> None:
        """Load persisted LSTM model and scaler from disk."""
        if self._model_path.exists() and self._scaler_path.exists():
            try:
                self.model = keras.models.load_model(self._model_path)
                self.scaler = joblib.load(self._scaler_path)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not load LSTM model due to {e}. A new one will be trained.")
                self.model = None


    def predict(self, series: pd.Series, horizon: int = 30, user_id: str | None = None) -> np.ndarray:
        """Iteratively forecast `horizon` days ahead. Returns inverse-transformed array."""
        _ = user_id  # Reserved for future per-user models.
        if horizon <= 0:
            return np.array([], dtype="float32")
        if series.empty:
            return self._baseline_forecast(series, horizon)

        clean = self._sanitize_series(series)
        if self.model is None:
            self.fit(clean)
        if self.model is None:
            # Still None if not enough data
            return self._baseline_forecast(clean, horizon)

        values = clean.values.reshape(-1, 1)
        try:
            scaled = self.scaler.transform(values)
        except Exception:
            # Recover from mismatched/corrupted persisted scaler.
            self.scaler.fit(values)
            scaled = self.scaler.transform(values)

        current_seq = self._seed_sequence(scaled)
        predictions = []
        try:
            for _ in range(horizon):
                pred = self.model.predict(current_seq, verbose=0)[0, 0]
                predictions.append(float(pred))
                # Shift window forward
                new_step = np.array([[[pred]]], dtype=current_seq.dtype)
                current_seq = np.concatenate([current_seq[:, 1:, :], new_step], axis=1)
        except Exception as e:
            self._logger.warning("LSTM prediction failed; using fallback forecasting. Error: %s", e)
            return self._baseline_forecast(clean, horizon)

        predictions_arr = np.array(predictions, dtype="float32").reshape(-1, 1)
        try:
            forecast = self.scaler.inverse_transform(predictions_arr).flatten()
        except Exception:
            forecast = predictions_arr.flatten()

        if not np.all(np.isfinite(forecast)):
            return self._baseline_forecast(clean, horizon)
        return forecast
