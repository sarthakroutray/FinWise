from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import config

_engine: Engine | None = None


def _get_engine() -> Engine:
    """Build and cache SQLAlchemy engine for documents metadata storage."""
    global _engine
    if _engine is None:
        candidates = [u for u in [config.NEON_DATABASE_URL, config.DB_URL] if u]
        if not candidates:
            raise RuntimeError("Neither NEON_DATABASE_URL nor DB_URL is configured")
        errors: list[str] = []
        for db_url in candidates:
            try:
                _engine = create_engine(db_url, pool_pre_ping=True)
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{db_url}: {exc}")
        if _engine is None:
            raise RuntimeError("Could not initialize any documents database engine. " + " | ".join(errors))
    return _engine


def ensure_documents_table() -> None:
    """Create per-user documents metadata table if it does not exist."""
    engine = _get_engine()
    with engine.begin() as conn:
        if engine.dialect.name == "sqlite":
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_documents (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_uid TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        mime_type TEXT,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    );
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS user_documents (
                        id BIGSERIAL PRIMARY KEY,
                        user_uid TEXT NOT NULL,
                        filename TEXT NOT NULL,
                        mime_type TEXT,
                        metadata_json JSONB NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
            )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_user_documents_user_uid_created_at
                    ON user_documents(user_uid, created_at DESC);
                """
            )
        )


def _json_safe(value: Any) -> Any:
    """Recursively convert values to strict JSON-compatible values."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value) if math.isfinite(value) else 0.0
    # numpy/pandas scalars and other objects
    try:
        num = float(value)
        return num if math.isfinite(num) else 0.0
    except Exception:
        return str(value)


def _encode_metadata(metadata: dict[str, Any]) -> str:
    safe = _json_safe(metadata)
    # allow_nan=False enforces strict JSON compliance.
    return json.dumps(safe, allow_nan=False)


def _decode_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except Exception:
            return {"value": value}
    return {}


def create_document(user_uid: str, filename: str, mime_type: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
    """Insert one document metadata row for a user."""
    ensure_documents_table()
    engine = _get_engine()
    metadata_json = _encode_metadata(metadata)
    if engine.dialect.name == "sqlite":
        insert_stmt = text(
            """
            INSERT INTO user_documents (user_uid, filename, mime_type, metadata_json)
            VALUES (:user_uid, :filename, :mime_type, :metadata_json);
            """
        )
    else:
        insert_stmt = text(
            """
            INSERT INTO user_documents (user_uid, filename, mime_type, metadata_json)
            VALUES (:user_uid, :filename, :mime_type, CAST(:metadata_json AS JSONB));
            """
        )

    select_stmt = text(
        """
        SELECT id, user_uid, filename, mime_type, metadata_json, created_at
        FROM user_documents
        WHERE id = :document_id;
        """
    )

    with engine.begin() as conn:
        result = conn.execute(
            insert_stmt,
            {
                "user_uid": user_uid,
                "filename": filename,
                "mime_type": mime_type,
                "metadata_json": metadata_json,
            },
        )
        inserted_id = result.lastrowid
        if inserted_id is None:
            # Fallback path for dialects that do not set lastrowid.
            inserted_id = conn.execute(text("SELECT MAX(id) AS id FROM user_documents")).scalar()
        row = conn.execute(select_stmt, {"document_id": inserted_id}).mappings().first()

    if not row:
        raise RuntimeError("Failed to insert document metadata")

    return {
        "id": int(row["id"]),
        "user_uid": row["user_uid"],
        "filename": row["filename"],
        "mime_type": row["mime_type"],
        "metadata": _decode_metadata(row["metadata_json"]),
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
            "metadata": _decode_metadata(r["metadata_json"]),
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
