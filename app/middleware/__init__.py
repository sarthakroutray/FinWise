"""
FastAPI middleware that logs per-request trace data.

Captures timing and metadata for debug-panel display.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TraceMiddleware(BaseHTTPMiddleware):
    """Attaches trace_id and timing to every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        request.state.trace_start = time.time()

        response = await call_next(request)

        elapsed_ms = round((time.time() - request.state.trace_start) * 1000)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time-Ms"] = str(elapsed_ms)

        logger.debug(
            "TRACE %s %s %s → %d in %dms",
            trace_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
