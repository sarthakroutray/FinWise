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
    active_keys = [
        k for k in [
            config.GEMINI_PRO_API_KEY, 
            config.GEMINI_FLASH_API_KEY_1, 
            config.GEMINI_FLASH_API_KEY_2
        ] if k and k.strip()
    ]
    
    if not active_keys:
        import logging
        logging.warning("No Gemini API keys found in config! Operations will fail.")

    # RAG index gets the pure Gemini client
    gemini_embedding_client = GeminiClient(
        api_keys=active_keys,
        model=config.GEMINI_PRO_MODEL,
    )
    
    # Use Groq for chatbot unconditionally
    groq_api_key = config.GROQ_API_KEY
    if not groq_api_key:
        groq_api_key = active_keys[0] if active_keys else ""
        
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
    llm_rag_index = LLMRagIndex(gemini_embedding_client)
