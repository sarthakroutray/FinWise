"""
Abstract base class for debate agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from app.llm.gemini_client import ChatEvent


@dataclass
class AgentContext:
    """Runtime context passed to every agent."""
    user_message: str
    rag_chunks: list[str] = field(default_factory=list)
    financial_data: dict[str, Any] = field(default_factory=dict)
    cashflow: float | None = None
    risk_tolerance: str = "moderate"  # "conservative" | "moderate" | "aggressive"


@dataclass
class AgentResponse:
    """Structured response from an agent."""
    pitch: str
    confidence: float
    key_points: list[str] = field(default_factory=list)
    raw_json: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Interface for debate agents."""

    name: str = "base"
    persona: str = "generic"

    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResponse:
        """Generate a complete response (non-streaming)."""
        ...

    @abstractmethod
    async def stream(self, context: AgentContext) -> AsyncGenerator[ChatEvent, None]:
        """Stream the response as ChatEvents."""
        ...
