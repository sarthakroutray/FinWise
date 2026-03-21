import numpy as np
import pandas as pd


def compute_health_score(
    df: pd.DataFrame,
    anomaly_df: pd.DataFrame,
    forecast: np.ndarray,
) -> dict:
    """Compute a 0-100 financial health score with grade and breakdown."""
    # Savings rate: (income - spend) / income
    total_income = df.loc[df["amount"] > 0, "amount"].sum()
    total_spend = df.loc[df["amount"] < 0, "amount"].abs().sum()
    savings_rate = (total_income - total_spend) / total_income if total_income > 0 else 0.0
    savings_rate = max(0.0, min(1.0, savings_rate))

    # Anomaly ratio
    anomaly_count = anomaly_df["is_anomaly"].sum() if "is_anomaly" in anomaly_df.columns else 0
    anomaly_ratio = anomaly_count / len(anomaly_df) if len(anomaly_df) > 0 else 0.0

    # Forecast trend via linear regression slope
    if len(forecast) >= 2:
        coeffs = np.polyfit(np.arange(len(forecast)), forecast, 1)
        slope = coeffs[0]
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
    score = round(max(0.0, min(100.0, score)), 2)

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
