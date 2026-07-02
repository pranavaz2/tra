"""
Request Identity — W3C Trace Context, API versioning, and deprecation headers.

Extends the base request ID middleware with:

  W3C Trace Context (RFC 3030 / https://www.w3.org/TR/trace-context/):
    traceparent  — 4-part trace identifier propagated across services.
                   Format: {version}-{trace-id}-{parent-id}-{flags}
    tracestate   — vendor-specific trace metadata (key=value pairs).

  API lifecycle headers (inbound, from OpenAPI/API gateway conventions):
    API-Version  — requested API version (e.g., "2024-01-01").
                   Useful for date-based API versioning alongside /api/v1/.
    Deprecation  — RFC 8594; date when the endpoint was deprecated
                   (e.g., "Sun, 01 Jan 2025 00:00:00 GMT").
    Sunset       — RFC 8594; date when the endpoint will be removed.

  These context vars are async-safe (ContextVar per async task) and are
  populated by RequestIdentityMiddleware before any route handler runs.

Usage:
    from app.core.middleware.request_identity import get_traceparent, get_api_version

    logger.info("Processing", extra={"traceparent": get_traceparent()})
    if get_api_version():
        # version-specific logic

Propagating traceparent to downstream services:
    In an HTTP client interceptor, read get_traceparent() and include
    it as the `traceparent` header on outgoing requests.

Middleware registration (in create_app()):
    app.add_middleware(RequestIdentityMiddleware)
    # Add AFTER RequestIDMiddleware so both run on every request.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# ── Header names ──────────────────────────────────────────────────────────── #

TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"
API_VERSION_HEADER = "API-Version"
DEPRECATION_HEADER = "Deprecation"
SUNSET_HEADER = "Sunset"

# ── ContextVars — async-safe, one per request ─────────────────────────────── #

_traceparent_ctx: ContextVar[str] = ContextVar("traceparent", default="")
_tracestate_ctx: ContextVar[str] = ContextVar("tracestate", default="")
_api_version_ctx: ContextVar[str] = ContextVar("api_version", default="")
_deprecation_ctx: ContextVar[str] = ContextVar("deprecation", default="")
_sunset_ctx: ContextVar[str] = ContextVar("sunset", default="")

# ── Traceparent format validation (W3C Trace Context) ─────────────────────── #
# version(2)-trace-id(32)-parent-id(16)-flags(2), hex, hyphen-separated.
_TRACEPARENT_RE = re.compile(
    r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$",
    re.ASCII,
)


# ── Public accessors ──────────────────────────────────────────────────────── #


def get_traceparent() -> str:
    """Return the W3C traceparent for the current async context (empty if absent)."""
    return _traceparent_ctx.get()


def get_tracestate() -> str:
    """Return the W3C tracestate for the current async context (empty if absent)."""
    return _tracestate_ctx.get()


def get_api_version() -> str:
    """Return the requested API-Version header value (empty if absent)."""
    return _api_version_ctx.get()


def get_deprecation() -> str:
    """Return the Deprecation header value for the current endpoint (empty if absent)."""
    return _deprecation_ctx.get()


def get_sunset() -> str:
    """Return the Sunset header value for the current endpoint (empty if absent)."""
    return _sunset_ctx.get()


def is_traceparent_valid(value: str) -> bool:
    """Return True if value conforms to the W3C Trace Context traceparent format."""
    return bool(value and _TRACEPARENT_RE.match(value))


# ── Middleware ────────────────────────────────────────────────────────────── #


class RequestIdentityMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that extracts and stores W3C trace context and API
    lifecycle headers for the duration of the request.

    Reads:
      traceparent, tracestate   — stored in ContextVars; echoed on responses.
      API-Version               — stored; used by version-routing logic.
      Deprecation, Sunset       — stored for optional response echoing.

    The traceparent is validated. Invalid values are discarded (not echoed)
    to prevent injection of malformed trace IDs into downstream systems.

    Ordering: register after RequestIDMiddleware in create_app() so both
    middlewares run on every request. Since Starlette applies middleware in
    reverse registration order, add this BEFORE RequestIDMiddleware in the
    add_middleware() call sequence.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw_traceparent = request.headers.get(TRACEPARENT_HEADER, "")
        tracestate = request.headers.get(TRACESTATE_HEADER, "")
        api_version = request.headers.get(API_VERSION_HEADER, "")
        deprecation = request.headers.get(DEPRECATION_HEADER, "")
        sunset = request.headers.get(SUNSET_HEADER, "")

        # Only propagate syntactically valid traceparent values.
        traceparent = raw_traceparent if is_traceparent_valid(raw_traceparent) else ""

        tp_tok = _traceparent_ctx.set(traceparent)
        ts_tok = _tracestate_ctx.set(tracestate)
        av_tok = _api_version_ctx.set(api_version)
        dp_tok = _deprecation_ctx.set(deprecation)
        su_tok = _sunset_ctx.set(sunset)

        try:
            response = await call_next(request)
        finally:
            _traceparent_ctx.reset(tp_tok)
            _tracestate_ctx.reset(ts_tok)
            _api_version_ctx.reset(av_tok)
            _deprecation_ctx.reset(dp_tok)
            _sunset_ctx.reset(su_tok)

        # Echo validated traceparent and tracestate so downstream trace collectors
        # can correlate response spans with the originating request.
        if traceparent:
            response.headers[TRACEPARENT_HEADER] = traceparent
        if tracestate and traceparent:
            response.headers[TRACESTATE_HEADER] = tracestate

        return response
