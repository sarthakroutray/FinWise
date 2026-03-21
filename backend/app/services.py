"""
Global singleton instances for shared state across routes.
Import these everywhere instead of creating new instances in each module.
"""
from app.models.anomaly import AnomalyDetector
from app.models.forecaster import LSTMForecaster
from app.rag.pipeline import RAGPipeline

# ── Existing singletons (parsing pipeline) ─────────────────────────────────
anomaly_detector = AnomalyDetector()
forecaster = LSTMForecaster()
rag_pipeline = RAGPipeline()

# ── LLM singletons (initialized lazily in init_gemini_services) ────────────
gemini_pro_client = None
gemini_flash_1_client = None
gemini_flash_2_client = None
session_manager = None
llm_rag_index = None


def init_gemini_services() -> None:
    """Create Gemini clients and LLM support services.

    Called once during app startup (lifespan).
    """
    global gemini_pro_client, gemini_flash_1_client, gemini_flash_2_client
    global session_manager, llm_rag_index

    from app.core.config import config
    from app.llm.gemini_client import GeminiClient
    from app.llm.groq_client import GroqClient
    from app.llm.conversation import SessionManager
    from app.llm.rag_index import LLMRagIndex

    # Pool all keys provided in .env to drastically enhance load-balanced rate limits
    raw_keys = [
        config.GEMINI_PRO_API_KEY,
        config.GEMINI_FLASH_API_KEY_1,
        config.GEMINI_FLASH_API_KEY_2,
        config.GEMINI_API_KEY,
    ]
    active_keys: list[str] = []
    for key in raw_keys:
        if key and key.strip() and key not in active_keys:
            active_keys.append(key)
    
    if not active_keys:
        import logging
        logging.warning("No Gemini API keys found in config! Operations will fail.")

    gemini_pro_client = GeminiClient(
        api_keys=active_keys,
        model=config.GEMINI_PRO_MODEL,
    )
    
    if getattr(config, "GROQ_API_KEY", None):
        gemini_flash_1_client = GroqClient(
            api_keys=config.GROQ_API_KEY,
            model="llama3-8b-8192",
        )
        gemini_flash_2_client = GroqClient(
            api_keys=config.GROQ_API_KEY,
            model="llama3-8b-8192",
        )
        import logging
        logging.info("Initialized high-speed Groq Llama3 backend for debate agents.")
    else:
        gemini_flash_1_client = GeminiClient(
            api_keys=active_keys,
            model=config.GEMINI_FLASH_MODEL,
        )
        gemini_flash_2_client = GeminiClient(
            api_keys=active_keys,
            model=config.GEMINI_FLASH_MODEL,
        )

    session_manager = SessionManager(ttl_seconds=3600 * 4)
    llm_rag_index = LLMRagIndex(gemini_pro_client)
