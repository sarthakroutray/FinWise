"""
Async wrapper around the Groq SDK for Llama models.
Provides: streaming chat, structured JSON output, and text.
Acts as a drop-in replacement for GeminiClient to bypass rate limits.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any, AsyncGenerator

from groq import AsyncGroq

from app.llm.gemini_client import ChatEvent

logger = logging.getLogger(__name__)


class GroqClient:
    """Thin async wrapper around Groq SDK, structurally matching GeminiClient."""

    def __init__(self, api_keys: str | list[str], model: str = "llama3-8b-8192") -> None:
        self.model = model
        
        if isinstance(api_keys, str):
            api_keys = [k.strip() for k in api_keys.split(",") if k.strip()]
            
        if not api_keys:
            raise ValueError("No Groq API keys provided.")
            
        self._clients = [AsyncGroq(api_key=k) for k in api_keys]

    @property
    def _client(self) -> AsyncGroq:
        """Randomly select a client instance to load-balance API requests."""
        return random.choice(self._clients)

    def _build_messages(self, messages: list[dict[str, str]], system_prompt: str | None) -> list[dict[str, str]]:
        formatted = []
        if system_prompt:
            formatted.append({"role": "system", "content": system_prompt})
        for msg in messages:
            role = msg.get("role", "user")
            if role == "model":
                role = "assistant"
            formatted.append({"role": role, "content": msg["content"]})
        return formatted

    # ── streaming chat ──────────────────────────────────────────────────

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[ChatEvent, None]:
        
        formatted_messages = self._build_messages(messages, system_prompt)
        
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield ChatEvent(kind="token", data=chunk.choices[0].delta.content)
            
            yield ChatEvent(kind="done")

        except Exception as exc:
            logger.exception("Groq stream error")
            yield ChatEvent(kind="error", data=str(exc))

    # ── single-shot JSON output ─────────────────────────────────────────

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.3,
    ) -> dict[str, Any]:
        """Non-streaming call that returns parsed JSON from the model."""
        formatted_messages = self._build_messages(messages, system_prompt)
        
        # Groq strongly recommends placing "JSON" in the system prompt
        if system_prompt:
            formatted_messages[0]["content"] += "\nEnsure you respond in valid JSON format."
        else:
            formatted_messages.insert(0, {"role": "system", "content": "Respond in strict JSON format."})
            
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            text = response.choices[0].message.content or "{}"
            return json.loads(text)
            
        except Exception as exc:
            logger.warning("Groq returned non-JSON or threw error: %s", exc)
            return {"raw_text": str(exc)}

    # ── single-shot plain text ──────────────────────────────────────────

    async def chat_text(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> str:
        formatted_messages = self._build_messages(messages, system_prompt)
        
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=formatted_messages,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Groq text error: %s", exc)
            return str(exc)
