"""
Per-conversation SQLite scratchpad.

Each session gets its own SQLite file at ``data/scratchpads/{session_id}.db``.
The user's financial transactions are optionally pre-loaded into a
``transactions`` table so the LLM can run SQL against real data.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import config

logger = logging.getLogger(__name__)


class ScratchpadDB:
    """File-backed SQLite database scoped to one conversation session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._dir = Path(config.SCRATCHPAD_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._dir / f"{session_id}.db"
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── Public API ──────────────────────────────────────────────────────

    def load_transactions(self, df: pd.DataFrame) -> int:
        """Load a transactions DataFrame into the ``transactions`` table.

        Columns are normalized to: date, description, amount, balance, category.
        Returns the number of rows inserted.
        """
        from app.llm.rag_index import normalize_columns

        norm = normalize_columns(df)
        norm.to_sql("transactions", self.conn, if_exists="replace", index=False)
        count = len(norm)
        logger.info("Loaded %d rows into scratchpad %s", count, self.session_id)
        return count

    def execute_sql(self, sql: str) -> dict[str, Any]:
        """Execute arbitrary SQL. Returns rows for SELECT, rowcount for DML."""
        try:
            cursor = self.conn.execute(sql)
            self.conn.commit()

            # For SELECT statements, return rows
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return {"columns": columns, "rows": rows, "rowcount": len(rows)}
            else:
                return {"rowcount": cursor.rowcount, "message": "OK"}

        except sqlite3.Error as exc:
            logger.warning("Scratchpad SQL error [%s]: %s", self.session_id, exc)
            return {"error": str(exc)}

    def list_tables(self) -> list[str]:
        """Return all table names in this scratchpad."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row[0] for row in cursor.fetchall()]

    def reset(self) -> None:
        """Drop all tables, effectively clearing the scratchpad."""
        tables = self.list_tables()
        for table in tables:
            self.conn.execute(f"DROP TABLE IF EXISTS [{table}]")
        self.conn.commit()
        logger.info("Reset scratchpad %s (%d tables dropped)", self.session_id, len(tables))

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def delete(self) -> None:
        """Close connection and remove the DB file."""
        self.close()
        if self._db_path.exists():
            self._db_path.unlink()
            logger.info("Deleted scratchpad file: %s", self._db_path)
