from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import config

_engine: Engine | None = None


def _get_engine() -> Engine:
    """Build and cache SQLAlchemy engine for Neon PostgreSQL."""
    global _engine
    if _engine is None:
        if not config.NEON_DATABASE_URL:
            raise RuntimeError("NEON_DATABASE_URL is not configured")
        _engine = create_engine(config.NEON_DATABASE_URL, pool_pre_ping=True)
    return _engine


def ensure_documents_table() -> None:
    """Create per-user documents metadata table if it does not exist."""
    engine = _get_engine()
    ddl = text(
        """
        CREATE TABLE IF NOT EXISTS user_documents (
            id BIGSERIAL PRIMARY KEY,
            user_uid TEXT NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT,
            metadata_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_user_documents_user_uid_created_at
            ON user_documents(user_uid, created_at DESC);
        """
    )
    with engine.begin() as conn:
        conn.execute(ddl)


def create_document(user_uid: str, filename: str, mime_type: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
    """Insert one document metadata row for a user."""
    ensure_documents_table()
    engine = _get_engine()
    stmt = text(
        """
        INSERT INTO user_documents (user_uid, filename, mime_type, metadata_json)
        VALUES (:user_uid, :filename, :mime_type, CAST(:metadata_json AS JSONB))
        RETURNING id, user_uid, filename, mime_type, metadata_json, created_at;
        """
    )
    with engine.begin() as conn:
        row = conn.execute(
            stmt,
            {
                "user_uid": user_uid,
                "filename": filename,
                "mime_type": mime_type,
                "metadata_json": json.dumps(metadata),
            },
        ).mappings().first()

    if not row:
        raise RuntimeError("Failed to insert document metadata")

    return {
        "id": int(row["id"]),
        "user_uid": row["user_uid"],
        "filename": row["filename"],
        "mime_type": row["mime_type"],
        "metadata": row["metadata_json"],
        "created_at": _to_iso(row["created_at"]),
    }


def list_documents(user_uid: str) -> list[dict[str, Any]]:
    """Fetch all document metadata rows for a user."""
    ensure_documents_table()
    engine = _get_engine()
    stmt = text(
        """
        SELECT id, user_uid, filename, mime_type, metadata_json, created_at
        FROM user_documents
        WHERE user_uid = :user_uid
        ORDER BY created_at DESC;
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(stmt, {"user_uid": user_uid}).mappings().all()

    return [
        {
            "id": int(r["id"]),
            "user_uid": r["user_uid"],
            "filename": r["filename"],
            "mime_type": r["mime_type"],
            "metadata": r["metadata_json"],
            "created_at": _to_iso(r["created_at"]),
        }
        for r in rows
    ]


def delete_document(user_uid: str, document_id: int) -> bool:
    """Delete one document metadata row belonging to a user."""
    ensure_documents_table()
    engine = _get_engine()
    stmt = text(
        """
        DELETE FROM user_documents
        WHERE id = :document_id AND user_uid = :user_uid;
        """
    )
    with engine.begin() as conn:
        result = conn.execute(stmt, {"document_id": document_id, "user_uid": user_uid})
    return (result.rowcount or 0) > 0


def _to_iso(value: Any) -> str:
    """Convert timestamp-like values to ISO string."""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
