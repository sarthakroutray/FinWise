"""
LLM-side vector index for financial data using Gemini embeddings + FAISS.

Completely separate from the existing app/rag/pipeline.py (which handles
PDF/CSV parsing).  This module works with *post-parsed* data only — either
a pandas DataFrame with transaction columns or raw text chunks.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import faiss

from app.llm.gemini_client import GeminiClient
from app.core.config import config

logger = logging.getLogger(__name__)

# ── Column aliases → canonical names ────────────────────────────────────────

_COLUMN_MAP: dict[str, str] = {
    # date
    "date": "date", "trans date": "date", "transaction date": "date",
    "txn date": "date", "posting date": "date", "value date": "date",
    "trans_date": "date", "transaction_date": "date",
    # description
    "description": "description", "desc": "description", "narration": "description",
    "details": "description", "particulars": "description", "memo": "description",
    "transaction description": "description", "remarks": "description",
    # amount
    "amount": "amount", "amt": "amount", "debit": "amount", "credit": "amount",
    "transaction amount": "amount", "txn amount": "amount", "value": "amount",
    "txn_amount": "amount", "transaction_amount": "amount",
    # balance
    "balance": "balance", "closing balance": "balance", "running balance": "balance",
    "balance_after": "balance", "closing_balance": "balance", "available balance": "balance",
    # category
    "category": "category", "type": "category", "transaction type": "category",
    "txn type": "category", "trans type": "category",
}

CANONICAL_COLUMNS = {"date", "description", "amount", "balance", "category"}


def normalize_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    """Map variant column names to canonical ones, drop extras."""
    import pandas as pd

    renamed: dict[str, str] = {}
    for col in df.columns:
        canonical = _COLUMN_MAP.get(col.strip().lower())
        if canonical and canonical not in renamed.values():
            renamed[col] = canonical

    df = df.rename(columns=renamed)

    # Keep only canonical columns that exist
    keep = [c for c in CANONICAL_COLUMNS if c in df.columns]
    extra = [c for c in df.columns if c not in CANONICAL_COLUMNS]
    if extra:
        logger.info("Dropping extra columns during normalization: %s", extra)

    return df[keep].copy()


def dataframe_to_chunks(df: "pd.DataFrame") -> list[str]:
    """Convert a normalized transaction DataFrame into semantic text chunks."""
    import pandas as pd

    chunks: list[str] = []

    # Row-level chunks
    for _, row in df.iterrows():
        parts = []
        if "date" in df.columns and pd.notna(row.get("date")):
            parts.append(f"On {row['date']}")
        if "description" in df.columns and pd.notna(row.get("description")):
            parts.append(str(row["description"]))
        if "amount" in df.columns and pd.notna(row.get("amount")):
            amt = float(row["amount"])
            parts.append(f"${amt:,.2f}")
        if "category" in df.columns and pd.notna(row.get("category")):
            parts.append(f"({row['category']})")
        if parts:
            chunks.append(": ".join(parts[:2]) + " " + " ".join(parts[2:]))

    # Category summaries
    if "category" in df.columns and "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        for cat, group in df.groupby("category"):
            total = group["amount"].sum()
            count = len(group)
            chunks.append(
                f"Category '{cat}': {count} transactions totalling ${abs(total):,.2f}"
            )

    # Monthly summaries
    if "date" in df.columns and "amount" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df_valid = df.dropna(subset=["date"])
        if not df_valid.empty:
            df_valid = df_valid.copy()
            df_valid["_month"] = df_valid["date"].dt.to_period("M")
            for period, group in df_valid.groupby("_month"):
                income = group.loc[group["amount"] > 0, "amount"].sum()
                spend = group.loc[group["amount"] < 0, "amount"].sum()
                chunks.append(
                    f"Month {period}: income=${income:,.2f}, spending=${abs(spend):,.2f}, net=${income + spend:,.2f}"
                )

    return chunks


class LLMRagIndex:
    """Gemini-embedding FAISS index (separate from the parsing-pipeline RAG)."""

    def __init__(self, gemini_client: GeminiClient) -> None:
        self._client = gemini_client
        self.index: faiss.IndexFlatL2 | None = None
        self.chunks: list[str] = []

    async def build_from_dataframe(self, df: "pd.DataFrame") -> None:
        """Normalize columns, chunk, embed, and build FAISS index."""
        norm_df = normalize_columns(df)
        chunks = dataframe_to_chunks(norm_df)
        if chunks:
            await self.build_from_chunks(chunks)

    async def build_from_chunks(self, chunks: list[str]) -> None:
        """Embed text chunks and build FAISS index."""
        if not chunks:
            return

        self.chunks = chunks

        # Batch embed (Gemini API may have limits — chunk in groups of 100)
        all_embeddings: list[list[float]] = []
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = await self._client.embed(batch)
            all_embeddings.extend(embeddings)

        arr = np.array(all_embeddings, dtype="float32")
        dim = arr.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(arr)
        logger.info("Built LLM RAG index: %d chunks, dim=%d", len(chunks), dim)

    async def query(self, question: str, top_k: int = 5) -> list[str]:
        """Return the top_k most relevant chunks for a question."""
        if self.index is None or not self.chunks:
            return []

        q_emb = await self._client.embed([question])
        q_arr = np.array(q_emb, dtype="float32")
        _, indices = self.index.search(q_arr, min(top_k, len(self.chunks)))
        return [self.chunks[i] for i in indices[0] if 0 <= i < len(self.chunks)]

    @property
    def is_ready(self) -> bool:
        return self.index is not None and len(self.chunks) > 0
