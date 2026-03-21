from typing import List, Any, Optional

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

from app.core.config import config


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline using FAISS + SentenceTransformer."""

    def __init__(self) -> None:
        self.encoder = SentenceTransformer(config.EMBEDDING_MODEL)
        self.index: faiss.IndexFlatL2 | None = None
        self.documents: List[str] = []
        self.full_context: str = ""
        self._last_df: Any = None

        # RLM is built lazily so provider/model can be changed per request.
        self._rlm_cls = None
        try:
            from app.rlm import RLM
            self._rlm_cls = RLM
        except Exception:
            self._rlm_cls = None

    def build_index(self, documents: List[str]) -> None:
        """Encode documents and add to FAISS flat L2 index."""
        self.documents = documents
        embeddings = self.encoder.encode(documents, convert_to_numpy=True).astype("float32")
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(embeddings)

    def query(self, question: str, top_k: int = 3) -> List[str]:
        """Return top_k most relevant documents for the question."""
        if self.index is None or not self.documents:
            return ["No documents indexed yet. Please upload a statement first."]
        q_emb = self.encoder.encode([question], convert_to_numpy=True).astype("float32")
        _, indices = self.index.search(q_emb, min(top_k, len(self.documents)))
        return [self.documents[i] for i in indices[0] if i < len(self.documents)]

    def set_full_context(self, df: Any) -> None:
        """Store a string representation of the full dataframe for RLM."""
        self._last_df = df
        # Clean representation for the LLM
        self.full_context = df.to_csv(index=False)

    def _parse_free_models(self) -> List[str]:
        return [m.strip() for m in config.OPENROUTER_FREE_MODELS.split(",") if m.strip()]

    def _build_rlm(self, provider: Optional[str], model: Optional[str]) -> Any:
        if self._rlm_cls is None:
            return None

        selected_provider = (provider or config.RLM_PROVIDER or "gemini").strip().lower()
        selected_model = (model or config.RLM_MODEL).strip()

        if selected_provider == "gemini" and not config.GEMINI_API_KEY:
            return None
        if selected_provider == "openrouter" and not config.OPENROUTER_API_KEY:
            return None

        return self._rlm_cls(
            provider=selected_provider,
            model=selected_model,
            recursive_model=config.RLM_RECURSIVE_MODEL,
            api_key=config.GEMINI_API_KEY,
            openrouter_api_key=config.OPENROUTER_API_KEY,
            openrouter_base_url=config.OPENROUTER_BASE_URL,
            openrouter_free_models=self._parse_free_models(),
        )

    async def query_rlm(self, question: str, provider: Optional[str] = None, model: Optional[str] = None) -> Any:
        """Use RLM for complex queries + visualization."""
        if not self.full_context:
            return "No document context available."

        rlm = self._build_rlm(provider=provider, model=model)
        if rlm is None:
            return "RLM is unavailable. Set RLM_PROVIDER and the matching API key (GEMINI_API_KEY or OPENROUTER_API_KEY) in backend .env."
        return await rlm.acomplete(question, self.full_context)
