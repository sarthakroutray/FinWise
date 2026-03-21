"""
Async wrapper around the google-genai SDK for Gemini models.

Provides: streaming chat, structured JSON output, and batch embedding.
Each client instance is bound to one API key + model pair — create
separate instances for Pro / Flash / Embedding usage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from google import genai
from google.genai import types

from app.core.config import config

logger = logging.getLogger(__name__)


# ── Lightweight event types emitted during streaming ────────────────────────

@dataclass
class ChatEvent:
    """A single server-sent event from a streaming chat."""
    kind: str  # "token" | "tool_call" | "done" | "error"
    data: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Client ──────────────────────────────────────────────────────────────────

class GeminiClient:
    """Thin async wrapper around google-genai for one model/key pair."""

    def __init__(self, api_keys: str | list[str], model: str) -> None:
        self.model = model
        
        if isinstance(api_keys, str):
            api_keys = [k.strip() for k in api_keys.split(",") if k.strip()]
            
        if not api_keys:
            raise ValueError("No Gemini API keys provided.")
            
        self._clients = [genai.Client(api_key=k) for k in api_keys]

    @property
    def _client(self) -> genai.Client:
        """Randomly select a client instance to load-balance API requests."""
        return random.choice(self._clients)

    # ── streaming chat ──────────────────────────────────────────────────

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[ChatEvent, None]:
        """Stream chat completion tokens as ChatEvent objects.

        Parameters
        ----------
        messages : list of {"role": "user"|"model", "content": str}
        system_prompt : optional system instruction
        tools : optional Gemini function declarations
        temperature : sampling temperature
        """
        contents = self._build_contents(messages)

        generate_kwargs: dict[str, Any] = {
            "model": self.model,
            "contents": contents,
            "config": types.GenerateContentConfig(
                temperature=temperature,
            ),
        }

        if system_prompt:
            generate_kwargs["config"].system_instruction = system_prompt

        if tools:
            generate_kwargs["config"].tools = tools

        try:
            response_stream = self._client.models.generate_content_stream(
                **generate_kwargs
            )
            for chunk in response_stream:
                # Handle function calls
                if chunk.candidates and chunk.candidates[0].content:
                    for part in chunk.candidates[0].content.parts:
                        if part.function_call:
                            fc = part.function_call
                            yield ChatEvent(
                                kind="tool_call",
                                data=fc.name,
                                metadata={"args": dict(fc.args) if fc.args else {}},
                            )
                        elif part.text:
                            yield ChatEvent(kind="token", data=part.text)

            yield ChatEvent(kind="done")

        except Exception as exc:
            logger.exception("Gemini stream error")
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
        contents = self._build_contents(messages)

        generate_kwargs: dict[str, Any] = {
            "model": self.model,
            "contents": contents,
            "config": types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        }

        if system_prompt:
            generate_kwargs["config"].system_instruction = system_prompt

        if tools:
            generate_kwargs["config"].tools = tools

        response = await asyncio.to_thread(
            self._client.models.generate_content, **generate_kwargs
        )

        text = response.text or "{}"
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Gemini returned non-JSON: %s", text[:200])
            return {"raw_text": text}

    # ── single-shot plain text ──────────────────────────────────────────

    async def chat_text(
        self,
        messages: list[dict[str, str]],
        *,
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
    ) -> str:
        """Non-streaming call that returns plain text."""
        contents = self._build_contents(messages)

        generate_kwargs: dict[str, Any] = {
            "model": self.model,
            "contents": contents,
            "config": types.GenerateContentConfig(
                temperature=temperature,
            ),
        }

        if system_prompt:
            generate_kwargs["config"].system_instruction = system_prompt

        if tools:
            generate_kwargs["config"].tools = tools

        response = await asyncio.to_thread(
            self._client.models.generate_content, **generate_kwargs
        )
        return response.text or ""

    # ── embeddings ──────────────────────────────────────────────────────

    async def embed(
        self,
        texts: list[str],
        *,
        model_override: str | None = None,
    ) -> list[list[float]]:
        """Embed a batch of texts via the Gemini Embedding API.

        Uses the embedding model from config by default.
        """
        embed_model = model_override or config.GEMINI_EMBEDDING_MODEL

        result = await asyncio.to_thread(
            self._client.models.embed_content,
            model=embed_model,
            contents=texts,
        )

        return [e.values for e in result.embeddings]

    # ── internals ───────────────────────────────────────────────────────

    @staticmethod
    def _build_contents(
        messages: list[dict[str, str]],
    ) -> list[types.Content]:
        """Convert simple dicts to google-genai Content objects."""
        contents: list[types.Content] = []
        for msg in messages:
            role = msg.get("role", "user")
            # Gemini uses "user" and "model" roles
            if role == "assistant":
                role = "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])],
                )
            )
        return contents
