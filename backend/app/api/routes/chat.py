"""
SSE-streaming chat endpoint.

POST /chat  →  Server-Sent Events stream

Handles:
- Normal standalone chat (Pro model)
- Tool calling (MCP math tools + scratchpad)
- Multi-agent debate (auto-triggered on low confidence or dilemma)
- Debug trace events
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import pandas as pd

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import config
from typing import Any, Union
from app.llm.gemini_client import GeminiClient, ChatEvent
from app.llm.groq_client import GroqClient
from app.llm.system_prompts import (
    STANDALONE_CHAT_PROMPT,
    TOOL_USAGE_INSTRUCTIONS,
    SCRATCHPAD_INSTRUCTIONS,
)
from app.llm.conversation import SessionManager
from app.llm.rag_index import LLMRagIndex
from app.mcp.tool_registry import get_tool_declarations, execute as execute_tool
from app.db.scratchpad import ScratchpadDB
from app.agents.base import AgentContext
from app.agents.saver_agent import SaverAgent
from app.agents.investor_agent import InvestorAgent
from app.agents.orchestrator import Orchestrator
from app.agents.router import (
    classify_message,
    check_confidence_trigger,
    should_trigger_debate,
    heuristic_is_dilemma,
)
from app.llm.rag_index import normalize_columns, dataframe_to_chunks

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Singletons (initialized in lifespan via services.py) ───────────────────

_pro_client: Union[GeminiClient, GroqClient] | None = None
_flash_client_1: Union[GeminiClient, GroqClient] | None = None
_flash_client_2: Union[GeminiClient, GroqClient] | None = None
_session_mgr: SessionManager | None = None
_rag_index: LLMRagIndex | None = None


def init_chat_services(
    pro: Union[GeminiClient, GroqClient],
    flash1: Union[GeminiClient, GroqClient],
    flash2: Union[GeminiClient, GroqClient],
    session_mgr: SessionManager,
    rag_index: Union[LLMRagIndex, None],
) -> None:
    """Called from app lifespan to inject dependencies."""
    global _pro_client, _flash_client_1, _flash_client_2, _session_mgr, _rag_index
    _pro_client = pro
    _flash_client_1 = flash1
    _flash_client_2 = flash2
    _session_mgr = session_mgr
    _rag_index = rag_index


# ── Request / Response Schemas ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    financial_context: dict[str, Any] | None = None


# ── SSE Helpers ─────────────────────────────────────────────────────────────

def _sse_event(event: str, data: Any) -> str:
    """Format a Server-Sent Event."""
    payload = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event}\ndata: {payload}\n\n"


# ── Main Chat Endpoint ─────────────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    SSE-streaming chat endpoint.

    Event types sent to the client:
    - token: incremental text token
    - tool_call: tool invocation notification
    - tool_result: result from tool (may include chart config)
    - chart: standalone chart config for the frontend
    - debate_start: multi-agent debate beginning
    - agent_pitch: {agent, tokens...} streamed pitch from debate agent
    - deliberation: orchestrator is evaluating
    - verdict: final verdict from orchestrator
    - debate_end: debate finished
    - debug: trace/timing metadata
    - done: stream complete
    - error: error occurred
    """
    return StreamingResponse(
        _stream_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_response(req: ChatRequest):
    """Main generator — routes between normal and debate modes."""
    t_start = time.time()
    trace: dict[str, Any] = {"trace_id": str(uuid.uuid4()), "stages": []}

    try:
        # Ensure services are initialized
        if not _pro_client or not _session_mgr:
            yield _sse_event("error", {"message": "Chat services not initialized"})
            return

        # Get or create session
        session = _session_mgr.get_or_create(req.session_id)
        session.add_message("user", req.message)

        # Convert request financial context into a dataframe (if provided)
        req_df: pd.DataFrame | None = None
        if req.financial_context and isinstance(req.financial_context, dict):
            tx = req.financial_context.get("transactions")
            if isinstance(tx, list) and tx:
                try:
                    req_df = pd.DataFrame(tx)
                except Exception as e:
                    logger.warning("Failed to parse request financial_context transactions: %s", e)

        # Ensure scratchpad exists
        if session.scratchpad is None:
            session.scratchpad = ScratchpadDB(req.session_id)

        # Ensure transactions are loaded into the scratchpad for SQL tool calls.
        # This is re-checked every request because a session may start before uploads occur.
        try:
            tables = set(session.scratchpad.list_tables())
            has_tx_table = "transactions" in tables
        except Exception:
            has_tx_table = False

        if not has_tx_table:
            from app.services import rag_pipeline

            df_source = req_df if req_df is not None else getattr(rag_pipeline, "_last_df", None)
            if df_source is not None:
                try:
                    session.scratchpad.load_transactions(df_source)

                    # Build LLM embedding index if needed
                    if _rag_index and not _rag_index.is_ready:
                        await _rag_index.build_from_dataframe(df_source)
                except Exception as e:
                    logger.error("Failed to inject transactions into chat scratchpad: %s", e)

        # RAG retrieval
        rag_chunks: list[str] = []
        if _rag_index and _rag_index.is_ready:
            t_rag = time.time()
            rag_chunks = await _rag_index.query(req.message, top_k=5)
            trace["stages"].append({"name": "rag_retrieval", "ms": round((time.time() - t_rag) * 1000), "chunks": len(rag_chunks)})
            session.set_rag_chunks(rag_chunks)
        elif req_df is not None and not req_df.empty:
            # Deterministic fallback when embedding index is not ready on this instance.
            try:
                fallback_chunks = dataframe_to_chunks(normalize_columns(req_df))
                rag_chunks = fallback_chunks[:5]
                trace["stages"].append({"name": "rag_fallback", "chunks": len(rag_chunks)})
                session.set_rag_chunks(rag_chunks)
            except Exception as e:
                logger.warning("Failed fallback RAG chunk generation: %s", e)

        # Quick routing check (heuristic first, then LLM if ambiguous)
        t_route = time.time()
        is_dilemma = heuristic_is_dilemma(req.message)
        # Router classification
        routing = None
        if not is_dilemma: # Only call LLM if heuristic didn't already classify as dilemma
            routing = await classify_message(_flash_client_1, req.message)
            is_dilemma = routing.mode == "debate" # Update is_dilemma based on LLM classification
        trace["stages"].append({"name": "routing", "ms": round((time.time() - t_route) * 1000), "mode": "debate" if is_dilemma else "normal"})

        if is_dilemma:
            # ── DEBATE MODE ────────────────────────────────────────────
            async for chunk in _run_debate(req, session, rag_chunks, trace):
                yield chunk
        else:
            # ── NORMAL MODE ────────────────────────────────────────────
            async for chunk in _run_normal(req, session, rag_chunks, trace):
                yield chunk

        # Final debug trace
        trace["total_ms"] = round((time.time() - t_start) * 1000)
        yield _sse_event("debug", trace)
        yield _sse_event("done", {"session_id": req.session_id})

    except Exception as exc:
        logger.exception("Chat stream error")
        yield _sse_event("error", {"message": str(exc)})


async def _run_normal(req: ChatRequest, session, rag_chunks: list[str], trace: dict):
    """Normal standalone chat with the Pro model."""
    rag_str = "\n".join(f"- {c}" for c in rag_chunks) if rag_chunks else "No financial data loaded yet."

    system_prompt = STANDALONE_CHAT_PROMPT.format(
        tool_instructions=TOOL_USAGE_INSTRUCTIONS,
        scratchpad_instructions=SCRATCHPAD_INSTRUCTIONS,
        rag_context=rag_str,
    )

    messages = session.get_history(max_messages=20)

    t_llm = time.time()
    full_response = ""

    # Build Gemini tool declarations
    tool_decls = [{"function_declarations": get_tool_declarations()}]

    async for event in _pro_client.stream_chat(
        messages,
        system_prompt=system_prompt,
        tools=tool_decls,
        temperature=0.7,
    ):
        if event.kind == "token":
            full_response += event.data
            yield _sse_event("token", {"text": event.data})

        elif event.kind == "tool_call":
            yield _sse_event("tool_call", {"name": event.data, "args": event.metadata.get("args", {})})

            # Execute the tool
            tool_result = execute_tool(
                event.data,
                event.metadata.get("args", {}),
                scratchpad=session.scratchpad,
                financial_context=req.financial_context,
            )

            # If it's a chart, we yield chart and STOP. The visual covers the answer.
            if isinstance(tool_result, dict) and tool_result.get("component_type") == "dynamic_chart":
                yield _sse_event("chart", tool_result)
                session.add_message("assistant", f"Generated chart: {event.data}")
                break
                
            # Otherwise, yield the tool result internally and FEED IT BACK TO THE LLM!
            yield _sse_event("tool_result", tool_result)
            
            # Agentic follow-up turn
            msg_history = list(messages)
            msg_history.append({"role": "assistant", "content": f"[Invoked tool {event.data} with args {json.dumps(event.metadata.get('args', {}))}]"})
            msg_history.append({"role": "user", "content": f"Tool result for {event.data}:\n```json\n{json.dumps(tool_result, default=str)}\n```\n\nPlease interpret this data and formulate a helpful text response for me."})
            
            async for followup in _pro_client.stream_chat(
                msg_history,
                system_prompt=system_prompt,
                tools=None,  # No recursive infinite tool calling for now
                temperature=0.7,
            ):
                if followup.kind == "token":
                    full_response += followup.data
                    yield _sse_event("token", {"text": followup.data})
            
            # Only allow one tool call turn in this basic implementation
            break

        elif event.kind == "error":
            yield _sse_event("error", {"message": event.data})

    trace["stages"].append({
        "name": "llm_generation",
        "ms": round((time.time() - t_llm) * 1000),
        "model": _pro_client.model,
        "tokens_approx": len(full_response.split()),
    })

    session.add_message("assistant", full_response)

    # Check if we should trigger a debate post-response
    confidence = check_confidence_trigger(full_response)
    trace["stages"].append({"name": "confidence_check", "confidence": confidence})

    if confidence is not None and should_trigger_debate(confidence):
        yield _sse_event("debate_trigger", {
            "confidence": confidence,
            "reason": f"Standalone confidence ({confidence:.0%}) below threshold",
        })


async def _run_debate(req: ChatRequest, session, rag_chunks: list[str], trace: dict):
    """Multi-agent debate flow: Saver → Investor → Orchestrator verdict."""
    yield _sse_event("debate_start", {
        "message": "Engaging financial advisors for a balanced analysis...",
        "agents": ["PennyWise (Saver)", "BullRun (Investor)"],
    })

    context = AgentContext(
        user_message=req.message,
        rag_chunks=rag_chunks,
        financial_data=req.financial_context or {},
    )

    # ── Phase 1: Run both agents in parallel ───────────────────────────
    saver = SaverAgent(_flash_client_1)
    investor = InvestorAgent(_flash_client_2)

    saver_text = ""
    investor_text = ""

    q = asyncio.Queue()

    async def run_agent(agent_name: str, agent_obj: Any, is_saver: bool) -> None:
        nonlocal saver_text, investor_text
        await q.put({"type": "agent_pitch", "agent": agent_name, "phase": "start"})
        try:
            async for event in agent_obj.stream(context):
                if event.kind == "token":
                    if is_saver:
                        saver_text += event.data
                    else:
                        investor_text += event.data
                    await q.put({"type": "agent_pitch", "agent": agent_name, "text": event.data})
        except Exception as e:
            logger.error("%s error: %s", agent_name, e)
        await q.put({"type": "agent_pitch", "agent": agent_name, "phase": "end"})

    t_agents = time.time()
    task1 = asyncio.create_task(run_agent("PennyWise", saver, True))
    task2 = asyncio.create_task(run_agent("BullRun", investor, False))
    tasks = [task1, task2]

    # Consumer loop
    while True:
        if all(t.done() for t in tasks) and q.empty():
            break
        try:
            event = await asyncio.wait_for(q.get(), timeout=0.1)
            event_type = event.pop("type")
            yield _sse_event(event_type, event)
            q.task_done()
        except asyncio.TimeoutError:
            continue

    trace["stages"].append({"name": "parallel_agents", "ms": round((time.time() - t_agents) * 1000)})

    # Pass agent confidences to frontend
    saver_conf = check_confidence_trigger(saver_text)
    if saver_conf is not None:
        yield _sse_event("agent_confidence", {"agent": "PennyWise", "score": round(saver_conf * 100)})
    
    investor_conf = check_confidence_trigger(investor_text)
    if investor_conf is not None:
        yield _sse_event("agent_confidence", {"agent": "BullRun", "score": round(investor_conf * 100)})

    # ── Phase 2: Orchestrator deliberation ─────────────────────────────
    yield _sse_event("deliberation", {"message": "Evaluating both perspectives..."})

    orchestrator = Orchestrator(_pro_client)
    t_verdict = time.time()

    verdict_text = ""
    yield _sse_event("verdict", {"phase": "start"})
    async for event in orchestrator.stream_verdict(
        user_dilemma=req.message,
        saver_pitch=saver_text,
        investor_pitch=investor_text,
        rag_chunks=rag_chunks,
    ):
        if event.kind == "token":
            verdict_text += event.data
            yield _sse_event("verdict", {"text": event.data})
    yield _sse_event("verdict", {"phase": "end"})

    verdict_conf = check_confidence_trigger(verdict_text)
    if verdict_conf is not None:
        yield _sse_event("agent_confidence", {"agent": "Arbiter", "score": round(verdict_conf * 100)})

    trace["stages"].append({"name": "orchestrator_verdict", "ms": round((time.time() - t_verdict) * 1000)})

    session.add_message("assistant", f"[DEBATE]\nSaver: {saver_text}\nInvestor: {investor_text}\nVerdict: {verdict_text}")

    yield _sse_event("debate_end", {"message": "Analysis complete"})
