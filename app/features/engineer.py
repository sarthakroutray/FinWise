import pandas as pd
import numpy as np

from app.features.categorizer import categorize_expenses


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived feature columns to the transaction DataFrame."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # Temporal features
    df["day_of_week"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6])
    df["month"] = df["date"].dt.month

    # Spending is negative amounts; compute rolling sums on absolute spend
    spend = df["amount"].apply(lambda x: abs(x) if x < 0 else 0.0)

    # Rolling spend windows (min_periods=1 so early rows still get values)
    df["rolling_7d_spend"] = spend.rolling(window=7, min_periods=1).sum()
    df["rolling_30d_spend"] = spend.rolling(window=30, min_periods=1).sum()

    # Spend velocity: ratio of 7d to 30d spend (avoid division by zero)
    df["spend_velocity"] = np.where(
        df["rolling_30d_spend"] > 0,
        df["rolling_7d_spend"] / df["rolling_30d_spend"],
        0.0,
    )

    # Z-score of amount column
    mean_amt = df["amount"].mean()
    std_amt = df["amount"].std()
    df["amount_zscore"] = np.where(std_amt > 0, (df["amount"] - mean_amt) / std_amt, 0.0)

    # Category assignment
    df["category"] = df["description"].apply(categorize_expenses)

    return df
