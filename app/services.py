"""
Global singleton instances for shared state across routes.
Import these everywhere instead of creating new instances in each module.
"""
from app.models.anomaly import AnomalyDetector
from app.models.forecaster import LSTMForecaster
from app.rag.pipeline import RAGPipeline

anomaly_detector = AnomalyDetector()
forecaster = LSTMForecaster()
rag_pipeline = RAGPipeline()
