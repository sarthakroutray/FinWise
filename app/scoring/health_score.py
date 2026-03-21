import numpy as np
import pandas as pd


def _safe_float(value: float, default: float = 0.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return num if np.isfinite(num) else default


def compute_health_score(
    df: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    forecast: np.ndarray,
) -> dict:
    """Compute a 0-100 financial health score with grade and breakdown."""
    # Savings rate: (income - spend) / income
    amount_series = pd.to_numeric(df["amount"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    total_income = amount_series[amount_series > 0].sum()
    total_spend = amount_series[amount_series < 0].abs().sum()
    savings_rate = (total_income - total_spend) / total_income if total_income > 0 else 0.0
    savings_rate = max(0.0, min(1.0, _safe_float(savings_rate)))

    # Anomaly ratio
    anomaly_count = pd.to_numeric(anomaly_df["is_anomaly"], errors="coerce").fillna(0).sum() if "is_anomaly" in anomaly_df.columns else 0
    anomaly_ratio = anomaly_count / len(anomaly_df) if len(anomaly_df) > 0 else 0.0
    anomaly_ratio = max(0.0, min(1.0, _safe_float(anomaly_ratio)))

    # Forecast trend via linear regression slope
    safe_forecast = np.asarray(forecast, dtype="float32")
    safe_forecast = np.where(np.isfinite(safe_forecast), safe_forecast, 0.0)
    if len(safe_forecast) >= 2:
        coeffs = np.polyfit(np.arange(len(safe_forecast)), safe_forecast, 1)
        slope = coeffs[0]
        if not np.isfinite(slope):
            slope = 0.0
        if slope > 0.01:
            forecast_trend = "improving"
            trend_bonus = 1.0
        elif slope < -0.01:
            forecast_trend = "declining"
            trend_bonus = 0.3
        else:
            forecast_trend = "stable"
            trend_bonus = 0.6
    else:
        forecast_trend = "stable"
        trend_bonus = 0.6

    # Composite score
    score = savings_rate * 40 + (1 - anomaly_ratio) * 30 + trend_bonus * 30
    score = round(max(0.0, min(100.0, _safe_float(score))), 2)

    # Grade mapping
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "savings_rate": round(savings_rate, 4),
        "anomaly_ratio": round(anomaly_ratio, 4),
        "forecast_trend": forecast_trend,
    }
