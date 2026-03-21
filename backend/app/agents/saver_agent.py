"""
Saver Agent — conservative "PennyWise" persona.

Uses gemini-3-flash (API key 1) to advocate for savings-first strategies.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Union

from app.agents.base import BaseAgent, AgentContext, AgentResponse
from app.llm.gemini_client import GeminiClient, ChatEvent
from app.llm.groq_client import GroqClient
from app.llm.system_prompts import SAVER_AGENT_PROMPT, TOOL_USAGE_INSTRUCTIONS, SCRATCHPAD_INSTRUCTIONS

logger = logging.getLogger(__name__)


class SaverAgent(BaseAgent):
    name = "PennyWise"
    persona = "saver"

    def __init__(self, client: Union[GeminiClient, GroqClient]) -> None:
        self._client = client

    def _build_prompt(self, context: AgentContext) -> str:
        rag_str = "\n".join(f"- {c}" for c in context.rag_chunks) if context.rag_chunks else "No data loaded."
        return SAVER_AGENT_PROMPT.format(
            tool_instructions=TOOL_USAGE_INSTRUCTIONS,
            scratchpad_instructions=SCRATCHPAD_INSTRUCTIONS,
            rag_context=rag_str,
        )

    async def run(self, context: AgentContext) -> AgentResponse:
        prompt = self._build_prompt(context)
        messages = [{"role": "user", "content": context.user_message}]

        result = await self._client.chat_json(messages, system_prompt=prompt)

        return AgentResponse(
            pitch=result.get("pitch", ""),
            confidence=float(result.get("confidence", 0.5)),
            key_points=result.get("key_points", []),
            raw_json=result,
        )

    async def stream(self, context: AgentContext) -> AsyncGenerator[ChatEvent, None]:
        prompt = self._build_prompt(context)
        messages = [{"role": "user", "content": context.user_message}]

        async for event in self._client.stream_chat(messages, system_prompt=prompt):
            yield event
