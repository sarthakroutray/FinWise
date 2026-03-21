import os
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import IsolationForest

from app.core.config import config


class AnomalyDetector:
    """IsolationForest-based anomaly detection on financial transactions."""

    def __init__(self, contamination: float = config.ANOMALY_CONTAMINATION) -> None:
        self.contamination = contamination
        self.model: IsolationForest | None = None
        self._model_path = Path(config.MODEL_DIR) / "isolation_forest.pkl"

    def fit(self, df: pd.DataFrame) -> None:
        """Train IsolationForest on engineered features and persist to disk."""
        if df.empty:
            return
        features = df[["amount_zscore", "rolling_7d_spend", "spend_velocity"]].fillna(0).values
        self.model = IsolationForest(
            contamination=self.contamination, random_state=42, n_estimators=200
        )
        self.model.fit(features)
        os.makedirs(config.MODEL_DIR, exist_ok=True)
        joblib.dump(self.model, self._model_path)

    def load(self) -> None:
        """Load persisted IsolationForest model from disk."""
        if self._model_path.exists():
            self.model = joblib.load(self._model_path)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Score transactions and flag anomalies."""
        df = df.copy()
        if df.empty:
            df["anomaly_score"] = []
            df["is_anomaly"] = []
            return df
            
        if self.model is None:
            self.fit(df)
            
        if self.model is None:
            df["anomaly_score"] = 0.0
            df["is_anomaly"] = False
            return df
            
        features = df[["amount_zscore", "rolling_7d_spend", "spend_velocity"]].fillna(0).values
        scores = self.model.decision_function(features)
        df["anomaly_score"] = scores
        df["is_anomaly"] = scores < -0.1
        return df
