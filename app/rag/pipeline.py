from typing import List, Any

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
        
        # Initialize RLM (Recursive Language Model)
        from app.rlm import RLM
        self.rlm = RLM(model="gpt-4o-mini")

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

    async def query_rlm(self, question: str) -> Any:
        """Use RLM for complex queries + visualization."""
        if not self.full_context:
            return "No document context available."
        return await self.rlm.acomplete(question, self.full_context)
