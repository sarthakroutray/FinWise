from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Central configuration via env vars or .env file."""
    APP_NAME: str = "FinWise AI"
    DEBUG: bool = False
    DB_URL: str = "sqlite:///./finwise.db"
    NEON_DATABASE_URL: str = ""
    MODEL_DIR: str = str(Path(__file__).resolve().parent.parent.parent / "models_store")
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 512
    ANOMALY_CONTAMINATION: float = 0.05
    LSTM_LOOKBACK: int = 30
    LSTM_EPOCHS: int = 50
    OCR_DPI: int = 300
    OCR_LANG: str = "eng"
    TESSERACT_CMD: str = ""
    NER_MODEL: str = "en_core_web_trf"
    PDF_PARSER: str = "auto"
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_CREDENTIALS_JSON: str = ""
    RLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    OPENROUTER_FREE_MODELS: str = ""
    RLM_MODEL: str = "gemini-1.5-flash"
    RLM_RECURSIVE_MODEL: str = "gemini-1.5-flash"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


config = Settings()
