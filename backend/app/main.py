from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import config
from app.api.routes import analyze, query, documents
from app.api.routes.anomaly import router as anomaly_router
from app.api.routes.chat import router as chat_router, init_chat_services
from app.api.routes.scratchpad import router as scratchpad_router
from app.middleware import TraceMiddleware
from app import services


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: load persisted models + init Gemini clients. Shutdown: no-op."""
    # Existing ML models
    services.anomaly_detector.load()
    services.forecaster.load()

    # Initialize Groq clients and LLM services
    services.init_llm_services()
    init_chat_services(
        pro=services.chat_pro_client,
        flash1=services.chat_flash_1_client,
        flash2=services.chat_flash_2_client,
        session_mgr=services.session_manager,
        rag_index=services.llm_rag_index,
    )

    yield


app = FastAPI(
    title=config.APP_NAME,
    description="Behavior-Aware Financial Advisor with Risk Intelligence",
    version="2.0.0",
    lifespan=lifespan,
)


def _resolve_cors_origins() -> list[str]:
    raw = (config.CORS_ORIGINS or "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    if config.DEBUG:
        return ["*"]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

# Trace middleware (must come before CORS)
app.add_middleware(TraceMiddleware)

# CORS: explicit origins in production; wildcard only in debug mode.
cors_origins = _resolve_cors_origins()
allow_credentials = not (len(cors_origins) == 1 and cors_origins[0] == "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id", "X-Response-Time-Ms"],
)

# Include routers
app.include_router(analyze.router, tags=["Analysis"])
app.include_router(query.router, tags=["Query"])
app.include_router(documents.router)
app.include_router(anomaly_router, tags=["Anomaly"])
app.include_router(chat_router, tags=["Chat"])
app.include_router(scratchpad_router)


@app.get("/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "app": config.APP_NAME,
        "groq_chat": bool(config.GROQ_API_KEY),
    }
