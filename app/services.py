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
    from app.llm.conversation import SessionManager
    from app.llm.rag_index import LLMRagIndex

    gemini_pro_client = GeminiClient(
        api_key=config.GEMINI_PRO_API_KEY,
        model=config.GEMINI_PRO_MODEL,
    )
    gemini_flash_1_client = GeminiClient(
        api_key=config.GEMINI_FLASH_API_KEY_1,
        model=config.GEMINI_FLASH_MODEL,
    )
    gemini_flash_2_client = GeminiClient(
        api_key=config.GEMINI_FLASH_API_KEY_2,
        model=config.GEMINI_FLASH_MODEL,
    )

    session_manager = SessionManager(ttl_seconds=3600 * 4)
    llm_rag_index = LLMRagIndex(gemini_pro_client)
