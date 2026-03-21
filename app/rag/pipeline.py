from typing import List

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
