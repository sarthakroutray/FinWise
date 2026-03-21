"""
Conversation session manager — holds message history, references to RAG
index, and scratchpad for a single chat session.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ConversationSession:
    """Holds state for one chat session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.messages: list[Message] = []
        self.created_at = time.time()
        self.last_active = time.time()
        # References set externally by the chat endpoint
        self.rag_index: Any = None  # LLMRagIndex
        self.scratchpad: Any = None  # ScratchpadDB

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.messages.append(Message(role=role, content=content, metadata=metadata or {}))
        self.last_active = time.time()

    def get_history(self, max_messages: int = 20) -> list[dict[str, str]]:
        """Return recent messages formatted for the Gemini API."""
        recent = self.messages[-max_messages:]
        return [
            {"role": m.role if m.role != "assistant" else "model", "content": m.content}
            for m in recent
            if m.role in ("user", "assistant", "model")
        ]

    def get_rag_context_str(self) -> str:
        """Get the latest RAG context as a formatted string (if available)."""
        if hasattr(self, "_last_rag_chunks") and self._last_rag_chunks:
            return "\n".join(f"- {c}" for c in self._last_rag_chunks)
        return "No financial data loaded yet."

    def set_rag_chunks(self, chunks: list[str]) -> None:
        self._last_rag_chunks = chunks


class SessionManager:
    """In-memory store of active conversation sessions with TTL cleanup."""

    def __init__(self, ttl_seconds: int = 3600 * 4) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._ttl = ttl_seconds

    def get_or_create(self, session_id: str) -> ConversationSession:
        self._cleanup()
        if session_id not in self._sessions:
            self._sessions[session_id] = ConversationSession(session_id)
            logger.info("Created new session: %s", session_id)
        return self._sessions[session_id]

    def get(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _cleanup(self) -> None:
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl
        ]
        for sid in expired:
            logger.info("Expiring session: %s", sid)
            del self._sessions[sid]
