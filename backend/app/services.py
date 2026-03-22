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

# ── LLM singletons (initialized lazily in init_llm_services) ────────────
chat_pro_client = None
chat_flash_1_client = None
chat_flash_2_client = None
session_manager = None
llm_rag_index = None


def init_llm_services() -> None:
    """Create Groq clients for chat and Gemini for embeddings.

    Called once during app startup (lifespan).
    """
    global chat_pro_client, chat_flash_1_client, chat_flash_2_client
    global session_manager, llm_rag_index

    from app.core.config import config
    from app.llm.gemini_client import GeminiClient
    from app.llm.groq_client import GroqClient
    from app.llm.conversation import SessionManager
    from app.llm.rag_index import LLMRagIndex

    # Pool all keys provided in .env to drastically enhance load-balanced rate limits
    raw_keys = [
        config.GEMINI_API_KEY,
    ]
    active_keys: list[str] = []
    for key in raw_keys:
        if key and key.strip() and key not in active_keys:
            active_keys.append(key)
    
    if not active_keys:
        import logging
        logging.warning("No Gemini API keys found in config! Operations will fail.")

    # RAG index gets the pure Gemini client, if keys are available
    if active_keys:
        gemini_embedding_client = GeminiClient(
            api_keys=active_keys,
            model=config.GEMINI_EMBEDDING_MODEL,
        )
        llm_rag_index = LLMRagIndex(gemini_embedding_client)
    else:
        llm_rag_index = None
    
    # Use Groq for chatbot unconditionally
    groq_api_key = config.GROQ_API_KEY
    if not groq_api_key:
        groq_api_key = active_keys[0] if active_keys else "dummy_key_to_allow_startup"
        
    chat_pro_client = GroqClient(
        api_keys=groq_api_key,
        model=config.GROQ_DEFAULT_MODEL,
    )
    chat_flash_1_client = GroqClient(
        api_keys=groq_api_key,
        model=config.GROQ_DEFAULT_MODEL,
    )
    chat_flash_2_client = GroqClient(
        api_keys=groq_api_key,
        model=config.GROQ_DEFAULT_MODEL,
    )

    session_manager = SessionManager(ttl_seconds=3600 * 4)
