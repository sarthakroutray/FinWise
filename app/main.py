from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import config
from app.api.routes import analyze, query
from app.models.anomaly import AnomalyDetector
from app.models.forecaster import LSTMForecaster
from app.rag.pipeline import RAGPipeline


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: load models if persisted. Shutdown: cleanup."""
    # Load pre-trained models on startup (no-op if files don't exist yet)
    detector = AnomalyDetector()
    detector.load()
    analyze._anomaly_detector = detector

    forecaster = LSTMForecaster()
    forecaster.load()
    analyze._forecaster = forecaster

    rag = RAGPipeline()
    analyze._rag_pipeline = rag
    query._rag_pipeline = rag

    yield


app = FastAPI(
    title=config.APP_NAME,
    description="Behavior-Aware Financial Advisor with Risk Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: allow all origins in dev mode
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analyze.router, tags=["Analysis"])
app.include_router(query.router, tags=["Query"])


@app.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "app": config.APP_NAME}
