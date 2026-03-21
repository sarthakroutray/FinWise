import numpy as np
import pandas as pd

from app.models.forecaster import LSTMForecaster


class _DummyModel:
    def predict(self, current_seq, verbose=0):
        _ = (current_seq, verbose)
        return np.array([[0.25]], dtype="float32")


def test_predict_non_positive_horizon_returns_empty_array():
    forecaster = LSTMForecaster(lookback=5, epochs=1)
    series = pd.Series([1.0, 2.0, 3.0], dtype="float32")

    result = forecaster.predict(series, horizon=0)

    assert isinstance(result, np.ndarray)
    assert result.size == 0


def test_predict_short_series_without_model_falls_back_to_last_value():
    forecaster = LSTMForecaster(lookback=30, epochs=1)
    series = pd.Series([10.0, np.nan, np.inf, 20.0], dtype="float32")

    result = forecaster.predict(series, horizon=4)

    assert result.shape == (4,)
    assert np.isfinite(result).all()
    assert np.allclose(result, np.array([20.0, 20.0, 20.0, 20.0], dtype="float32"))


def test_predict_short_series_with_model_handles_padding():
    forecaster = LSTMForecaster(lookback=30, epochs=1)
    forecaster.model = _DummyModel()

    raw_values = np.arange(1, 29, dtype="float32")
    series = pd.Series(raw_values)

    forecaster.scaler.fit(raw_values.reshape(-1, 1))

    result = forecaster.predict(series, horizon=3)

    assert result.shape == (3,)
    assert np.isfinite(result).all()
