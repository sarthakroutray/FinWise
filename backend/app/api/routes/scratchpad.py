"""
REST endpoints for the per-conversation SQLite scratchpad.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.scratchpad import ScratchpadDB

router = APIRouter(prefix="/scratchpad", tags=["Scratchpad"])


class SQLRequest(BaseModel):
    session_id: str
    sql: str


@router.post("/query")
async def scratchpad_query(req: SQLRequest) -> dict:
    """Execute SQL on a session's scratchpad."""
    db = ScratchpadDB(req.session_id)
    return db.execute_sql(req.sql)


@router.get("/tables/{session_id}")
async def scratchpad_tables(session_id: str) -> dict:
    """List all tables in a session's scratchpad."""
    db = ScratchpadDB(session_id)
    return {"tables": db.list_tables()}


@router.post("/reset/{session_id}")
async def scratchpad_reset(session_id: str) -> dict:
    """Drop all tables in a session's scratchpad."""
    db = ScratchpadDB(session_id)
    db.reset()
    return {"status": "ok", "message": f"Scratchpad {session_id} reset"}
