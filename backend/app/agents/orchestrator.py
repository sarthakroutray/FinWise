"""
Orchestrator — evaluates Saver + Investor pitches and renders a final verdict.

Uses gemini-3.1-pro-preview for higher-quality reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Union

from app.agents.base import AgentContext
from app.llm.gemini_client import GeminiClient, ChatEvent
from app.llm.groq_client import GroqClient
from app.llm.system_prompts import ORCHESTRATOR_PROMPT, STREAMING_ORCHESTRATOR_PROMPT

logger = logging.getLogger(__name__)


class Orchestrator:
    """Pro-model evaluator for multi-agent debates."""

    def __init__(self, client: Union[GeminiClient, GroqClient]) -> None:
        self._client = client

    async def evaluate(
        self,
        user_dilemma: str,
        saver_pitch: str,
        investor_pitch: str,
        rag_chunks: list[str],
    ) -> dict[str, Any]:
        """Generate a structured verdict (non-streaming)."""
        rag_str = "\n".join(f"- {c}" for c in rag_chunks) if rag_chunks else "No financial data loaded."

        prompt = ORCHESTRATOR_PROMPT.format(
            saver_pitch=saver_pitch,
            investor_pitch=investor_pitch,
            rag_context=rag_str,
            user_dilemma=user_dilemma,
        )

        messages = [{"role": "user", "content": f"Please evaluate the debate about: {user_dilemma}"}]

        result = await self._client.chat_json(messages, system_prompt=prompt, temperature=0.4)

        # Ensure required fields
        result.setdefault("debate_status", "resolved")
        result.setdefault("confidence_score", 0.5)
        result.setdefault("final_verdict", "Unable to reach a verdict.")

        return result

    async def stream_verdict(
        self,
        user_dilemma: str,
        saver_pitch: str,
        investor_pitch: str,
        rag_chunks: list[str],
    ) -> AsyncGenerator[ChatEvent, None]:
        """Stream the verdict for real-time UI rendering."""
        rag_str = "\n".join(f"- {c}" for c in rag_chunks) if rag_chunks else "No financial data loaded."

        prompt = STREAMING_ORCHESTRATOR_PROMPT.format(
            saver_pitch=saver_pitch,
            investor_pitch=investor_pitch,
            rag_context=rag_str,
            user_dilemma=user_dilemma,
        )

        messages = [{"role": "user", "content": f"Please evaluate the debate about: {user_dilemma}"}]

        async for event in self._client.stream_chat(messages, system_prompt=prompt, temperature=0.4):
            yield event
