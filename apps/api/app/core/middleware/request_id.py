"""
Travix AI — Request ID & Correlation ID Middleware

Assigns a unique request_id to every inbound HTTP request and propagates
it through the async context so all log lines within that request carry
the same ID without explicit parameter threading.

request_id
  Unique per HTTP request. Sourced from the X-Request-ID inbound header
  (set by load balancers or API gateways) or generated as UUID v4.
  Always echoed in the X-Request-ID response header.

correlation_id
  Links async background work back to the originating request.
  When a job is enqueued, pass the current request_id as correlation_id
  in the job arguments. The ARQ worker reads it and stores it here.
  Passed through via the X-Correlation-ID header if present.

Usage in application code:
    from app.core.middleware.request_id import get_request_id, get_correlation_id

    logger.info("Processing trip", extra={"request_id": get_request_id()})
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"
CORRELATION_ID_HEADER = "X-Correlation-ID"

# ContextVars are async-safe: each request gets its own copy
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_request_id() -> str:
    """Return the request ID for the current async context."""
    return _request_id_ctx.get()


def get_correlation_id() -> str:
    """Return the correlation ID for the current async context."""
    return _correlation_id_ctx.get()


def set_correlation_id(value: str) -> None:
    """
    Set the correlation ID for the current async context.

    Called by ARQ workers when processing a job that carries a
    correlation_id from the originating HTTP request.
    """
    _correlation_id_ctx.set(value)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that assigns request and correlation IDs.

    Add this middleware last in create_app() so it executes first on requests,
    ensuring all subsequent middleware and route handlers have access to the IDs.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        correlation_id = request.headers.get(CORRELATION_ID_HEADER, "")

        rid_token = _request_id_ctx.set(request_id)
        cid_token = _correlation_id_ctx.set(correlation_id)

        try:
            response = await call_next(request)
        finally:
            _request_id_ctx.reset(rid_token)
            _correlation_id_ctx.reset(cid_token)

        response.headers[REQUEST_ID_HEADER] = request_id
        if correlation_id:
            response.headers[CORRELATION_ID_HEADER] = correlation_id

        return response
