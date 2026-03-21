"""
Router — decides whether a user message should be handled by the
normal standalone agent or trigger a multi-agent debate.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Union

from app.llm.gemini_client import GeminiClient
from app.llm.groq_client import GroqClient
from app.llm.system_prompts import ROUTER_CLASSIFICATION_PROMPT

logger = logging.getLogger(__name__)

# Confidence threshold: below this triggers debate mode
DEBATE_CONFIDENCE_THRESHOLD = 0.70

# Quick heuristic keywords that suggest a dilemma (before LLM classification)
_DILEMMA_KEYWORDS = {
    "should i", "invest or save", "save or invest", "buy or rent",
    "worth it", "afford", "dilemma", "decide between", "better option",
    "risk", "what would you do", "vs", "versus", "or should",
}


@dataclass
class RoutingDecision:
    mode: str  # "normal" | "debate"
    trigger_reason: str
    confidence: float | None = None


def check_confidence_trigger(response_text: str) -> float | None:
    """Extract confidence score from the hidden JSON block in a response."""
    # Look for ```json\n{"confidence": 0.XX}\n```
    match = re.search(r'\{"confidence":\s*([\d.]+)\}', response_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


def heuristic_is_dilemma(message: str) -> bool:
    """Fast keyword check before calling the LLM classifier."""
    lower = message.lower()
    return any(kw in lower for kw in _DILEMMA_KEYWORDS)


async def classify_message(
    client: Union[GeminiClient, GroqClient],
    user_message: str,
) -> RoutingDecision:
    """Use LLM to classify a message as normal or debate-worthy.

    Falls back to heuristic if LLM classification fails.
    """
    # Fast path: obvious dilemma keywords
    if heuristic_is_dilemma(user_message):
        return RoutingDecision(
            mode="debate",
            trigger_reason="Message contains financial dilemma keywords",
        )

    # LLM classification
    try:
        prompt = ROUTER_CLASSIFICATION_PROMPT.format(user_message=user_message)
        result = await client.chat_json(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        score = result.get("debate_worthiness_score", 0)
        reason = result.get("reason", "LLM classification")

        # Threshold check
        mode = "debate" if score >= 70 else "normal"

        return RoutingDecision(
            mode=mode,
            trigger_reason=f"{reason} (Score: {score}/100)",
        )

    except Exception as exc:
        logger.warning("Router classification failed, defaulting to normal: %s", exc)
        return RoutingDecision(mode="normal", trigger_reason="Classification fallback")


def should_trigger_debate(
    confidence: float | None,
    routing: RoutingDecision | None = None,
) -> bool:
    """Determine if the debate should be triggered based on confidence + routing."""
    # Explicit debate classification
    if routing and routing.mode == "debate":
        return True

    # Low confidence from standalone response
    if confidence is not None and confidence < DEBATE_CONFIDENCE_THRESHOLD:
        return True

    return False
