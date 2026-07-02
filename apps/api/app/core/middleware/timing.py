"""
Travix AI — Request Timing Middleware

Measures the wall-clock time each request takes from first byte received to
last byte of the response. Adds the result as an X-Response-Time header.

Also logs a structured WARNING for requests that exceed the slow-request
threshold so they are surfaced in monitoring dashboards without noise.

Header format:
  X-Response-Time: 42.7ms

Slow-request threshold: configurable, defaults to 500ms.
Health-check endpoints (/health, /ready, /live) are excluded from slow-request
warnings because they are called at high frequency by infrastructure tooling.
"""

from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

RESPONSE_TIME_HEADER = "X-Response-Time"

_SLOW_REQUEST_THRESHOLD_MS: float = 500.0
_HEALTH_PATHS: frozenset[str] = frozenset({"/health", "/ready", "/live"})


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Injects X-Response-Time header and warns on slow requests.

    Register this middleware after RequestIDMiddleware in create_app() so it
    executes second on requests (immediately after IDs are assigned).
    """

    def __init__(self, app: object, slow_threshold_ms: float = _SLOW_REQUEST_THRESHOLD_MS) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._slow_threshold_ms = slow_threshold_ms

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start_ns = time.monotonic_ns()

        response = await call_next(request)

        elapsed_ms = (time.monotonic_ns() - start_ns) / 1_000_000
        response.headers[RESPONSE_TIME_HEADER] = f"{elapsed_ms:.1f}ms"

        if elapsed_ms > self._slow_threshold_ms and request.url.path not in _HEALTH_PATHS:
            logger.warning(
                "Slow request detected",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": round(elapsed_ms, 1),
                    "threshold_ms": self._slow_threshold_ms,
                },
            )

        return response
