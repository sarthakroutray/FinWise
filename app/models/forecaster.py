"""
Production-ready hybrid LSTM forecaster for financial spending prediction.

Strategy:
  - Per-user LSTM if user has >= MIN_USER_DAYS of daily data
  - Global LSTM fallback if a global model is pre-trained
  - Exponential smoothing baseline as final fallback
"""
import os
import logging
from pathlib import Path
from typing import Tuple, Optional

import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
from sklearn.preprocessing import MinMaxScaler

from app.core.config import config

logger = logging.getLogger(__name__)

# Minimum days of data required to train a per-user model
_MIN_USER_DAYS = max(config.LSTM_LOOKBACK * 2, 60)
_GLOBAL_MODEL_ID = "global"


def prepare_data(series: pd.Series) -> Tuple[np.ndarray, MinMaxScaler]:
    """Resample to daily, fill gaps with 0, scale to [0,1]. Returns (scaled_array, scaler)."""
    daily = series.resample("D").sum().fillna(0)
    values = daily.values.reshape(-1, 1).astype("float32")
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled = scaler.fit_transform(values)
    return scaled, scaler


def create_sequences(data: np.ndarray, window_size: int) -> Tuple[np.ndarray, np.ndarray]:
    """Sliding window sequences: X shape=(n, window, 1), y shape=(n,)."""
    X, y = [], []
    for i in range(len(data) - window_size):
        X.append(data[i : i + window_size])
        y.append(data[i + window_size])
    return np.array(X), np.array(y)


def build_model(input_shape: tuple) -> tf.keras.Model:
    """Lightweight 2-layer LSTM with dropout. Compiled with Adam + Huber loss."""
    model = tf.keras.Sequential([
        tf.keras.layers.LSTM(32, return_sequences=True, input_shape=input_shape),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(16, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(1),
    ])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=tf.keras.losses.Huber(),  # robust to outliers vs MSE
    )
    return model


def _model_dir() -> Path:
    path = Path(config.MODEL_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _model_path(user_id: str) -> Path:
    return _model_dir() / f"user_{user_id}.keras"


def _scaler_path(user_id: str) -> Path:
    return _model_dir() / f"user_{user_id}_scaler.pkl"


def _global_model_path() -> Path:
    return _model_dir() / "global_lstm.keras"


def _global_scaler_path() -> Path:
    return _model_dir() / "global_lstm_scaler.pkl"


def _exp_smoothing_forecast(series_values: np.ndarray, steps: int, alpha: float = 0.3) -> np.ndarray:
    """Exponential smoothing fallback — no ML required."""
    s = float(series_values[0])
    for v in series_values[1:]:
        s = alpha * float(v) + (1 - alpha) * s
    return np.full(steps, s, dtype="float32")


def _train_lstm(
    scaled: np.ndarray, window: int, epochs: int
) -> Tuple[tf.keras.Model, list]:
    """Fit LSTM with EarlyStopping + ReduceLR. Returns (model, history)."""
    X, y = create_sequences(scaled, window)
    if len(X) == 0:
        return None, []
    X = X.reshape(X.shape[0], X.shape[1], 1)
    model = build_model((window, 1))
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="loss", patience=5, restore_best_weights=True, verbose=0
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="loss", factor=0.5, patience=3, min_lr=1e-6, verbose=0
        ),
    ]
    model.fit(
        X, y,
        epochs=epochs,
        batch_size=8,
        callbacks=callbacks,
        verbose=0,
    )
    return model, model.history.history.get("loss", [])


def _iterative_predict(
    model: tf.keras.Model,
    scaler: MinMaxScaler,
    seed_scaled: np.ndarray,
    steps: int,
    window: int,
) -> np.ndarray:
    """Multi-step forecast by iteratively feeding predictions back as input."""
    seq = seed_scaled[-window:].reshape(1, window, 1)
    preds = []
    for _ in range(steps):
        p = model.predict(seq, verbose=0)[0, 0]
        preds.append(p)
        seq = np.concatenate([seq[:, 1:, :], [[[p]]]], axis=1)
    return scaler.inverse_transform(np.array(preds).reshape(-1, 1)).flatten()


def train_or_load_model(
    user_id: str,
    series: pd.Series,
    force_retrain: bool = False,
) -> Tuple[Optional[tf.keras.Model], Optional[MinMaxScaler], str]:
    """
    Hybrid strategy:
      1. Per-user model if >= MIN_USER_DAYS data and model missing/stale.
      2. Global model if per-user data is insufficient.
      3. None (triggers exp-smoothing fallback) if no global model exists.

    Returns (model, scaler, strategy_used).
    """
    window = config.LSTM_LOOKBACK
    epochs = config.LSTM_EPOCHS
    daily = series.resample("D").sum().fillna(0)
    n_days = len(daily)

    # --- Attempt per-user model ---
    if n_days >= _MIN_USER_DAYS:
        mp = _model_path(user_id)
        sp = _scaler_path(user_id)
        if not force_retrain and mp.exists() and sp.exists():
            logger.info("Loading per-user model for user=%s", user_id)
            return tf.keras.models.load_model(mp), joblib.load(sp), "per_user_cached"
        # Train per-user model
        scaled, scaler = prepare_data(daily)
        model, _ = _train_lstm(scaled, window, epochs)
        if model is not None:
            model.save(mp)
            joblib.dump(scaler, sp)
            logger.info("Trained & saved per-user model for user=%s", user_id)
            return model, scaler, "per_user_trained"

    # --- Fallback: global model ---
    gmp = _global_model_path()
    gsp = _global_scaler_path()
    if gmp.exists() and gsp.exists():
        logger.info("Using global LSTM model for user=%s (only %d days)", user_id, n_days)
        # Fine-tune global model on available user data if there's enough for a window
        if n_days > window:
            model = tf.keras.models.load_model(gmp)
            scaler = joblib.load(gsp)
            scaled = scaler.transform(daily.values.reshape(-1, 1).astype("float32"))
            X, y = create_sequences(scaled, window)
            if len(X) > 0:
                X = X.reshape(X.shape[0], X.shape[1], 1)
                model.fit(X, y, epochs=min(10, epochs), batch_size=8, verbose=0)
            return model, scaler, "global_finetuned"
        return tf.keras.models.load_model(gmp), joblib.load(gsp), "global_cached"

    # --- No model anywhere; caller will use exp-smoothing ---
    logger.warning("No model available for user=%s; will use exp-smoothing fallback.", user_id)
    return None, None, "fallback"


def predict_future(
    user_id: str,
    series: pd.Series,
    steps: int = 30,
    force_retrain: bool = False,
) -> np.ndarray:
    """
    Forecast `steps` days ahead for the given user.
    Automatically selects strategy and applies fallback if needed.
    """
    daily = series.resample("D").sum().fillna(0)
    model, scaler, strategy = train_or_load_model(user_id, series, force_retrain)

    if model is None or len(daily) <= config.LSTM_LOOKBACK:
        # Exponential smoothing fallback
        logger.info("exp-smoothing fallback for user=%s (strategy=%s)", user_id, strategy)
        return _exp_smoothing_forecast(daily.values, steps)

    scaled = scaler.transform(daily.values.reshape(-1, 1).astype("float32"))
    logger.info("Predicting %d steps for user=%s (strategy=%s)", steps, user_id, strategy)
    return _iterative_predict(model, scaler, scaled, steps, config.LSTM_LOOKBACK)


# ---------------------------------------------------------------------------
# LSTMForecaster class — maintains backward-compat with app/services.py
# ---------------------------------------------------------------------------
class LSTMForecaster:
    """Thin wrapper over the functional API. Preserves the interface used by analyze.py."""

    def __init__(
        self,
        lookback: int = config.LSTM_LOOKBACK,
        epochs: int = config.LSTM_EPOCHS,
    ) -> None:
        self.lookback = lookback
        self.epochs = epochs
        # Expose paths so the notebook can still reference them
        self._model_path = _global_model_path()
        self._scaler_path = _global_scaler_path()

    def fit(self, series: pd.Series, user_id: str = _GLOBAL_MODEL_ID) -> None:
        """Train and persist a model for the given user_id (default = global)."""
        daily = series.resample("D").sum().fillna(0)
        scaled, scaler = prepare_data(daily)
        model, _ = _train_lstm(scaled, self.lookback, self.epochs)
        if model is None:
            logger.warning("Not enough data to train LSTM (user=%s).", user_id)
            return
        if user_id == _GLOBAL_MODEL_ID:
            model.save(_global_model_path())
            joblib.dump(scaler, _global_scaler_path())
        else:
            model.save(_model_path(user_id))
            joblib.dump(scaler, _scaler_path(user_id))

    def load(self, user_id: str = _GLOBAL_MODEL_ID) -> None:
        """Pre-load check — actual loading happens lazily inside predict_future."""
        pass  # lazy loading is handled by train_or_load_model

    def predict(
        self,
        series: pd.Series,
        horizon: int = 30,
        user_id: str = "default",
    ) -> np.ndarray:
        """Forecast `horizon` days for the given user. Falls back gracefully."""
        return predict_future(user_id=user_id, series=series, steps=horizon)
