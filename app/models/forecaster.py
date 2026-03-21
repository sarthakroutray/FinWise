import os
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
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
        self.model: tf.keras.Model | None = None
        self.scaler: MinMaxScaler = MinMaxScaler()
        self._model_path = Path(config.MODEL_DIR) / "lstm_forecaster.keras"
        self._scaler_path = Path(config.MODEL_DIR) / "lstm_scaler.pkl"

    def _build_model(self, input_shape: tuple) -> tf.keras.Model:
        """Construct a 2-layer LSTM architecture."""
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(64, return_sequences=True, input_shape=input_shape),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.LSTM(32, return_sequences=False),
            tf.keras.layers.Dropout(0.2),
            tf.keras.layers.Dense(1),
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
        values = series.values.reshape(-1, 1).astype("float32")
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

    def load(self) -> None:
        """Load persisted LSTM model and scaler from disk."""
        if self._model_path.exists() and self._scaler_path.exists():
            self.model = tf.keras.models.load_model(self._model_path)
            self.scaler = joblib.load(self._scaler_path)

    def predict(self, series: pd.Series, horizon: int = 30) -> np.ndarray:
        """Iteratively forecast `horizon` days ahead. Returns inverse-transformed array."""
        if self.model is None:
            self.fit(series)
        if self.model is None:
            # Still None if not enough data
            return np.zeros(horizon)
        values = series.values.reshape(-1, 1).astype("float32")
        scaled = self.scaler.transform(values)
        # Seed sequence is last `lookback` values
        current_seq = scaled[-self.lookback:].reshape(1, self.lookback, 1)
        predictions = []
        for _ in range(horizon):
            pred = self.model.predict(current_seq, verbose=0)[0, 0]
            predictions.append(pred)
            # Shift window forward
            new_step = np.array([[[pred]]])
            current_seq = np.concatenate([current_seq[:, 1:, :], new_step], axis=1)
        predictions_arr = np.array(predictions).reshape(-1, 1)
        return self.scaler.inverse_transform(predictions_arr).flatten()
