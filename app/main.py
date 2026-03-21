from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import config
from app.api.routes import analyze, query
from app import services


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: load persisted models into shared singletons. Shutdown: no-op."""
    services.anomaly_detector.load()
    services.forecaster.load()
    # RAGPipeline index is rebuilt per request — no persistent load needed
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

app.include_router(analyze.router, tags=["Analysis"])
app.include_router(query.router, tags=["Query"])


@app.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "healthy", "app": config.APP_NAME}
