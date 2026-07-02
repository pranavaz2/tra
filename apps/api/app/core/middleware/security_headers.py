"""
Travix AI — Security Headers Middleware

Adds HTTP security headers to every response. These headers instruct browsers
and proxies to enforce secure behaviour even when the application does not
explicitly set them in route handlers.

Headers applied to ALL responses:
  X-Content-Type-Options: nosniff
    Prevents browsers from MIME-sniffing the content type.

  X-Frame-Options: DENY
    Prevents the response from being embedded in an iframe.
    Relevant for the /docs endpoint (Swagger UI) in non-production.

  X-XSS-Protection: 0
    Disables the legacy IE/Chrome XSS filter — modern guidance is to disable
    it and rely on Content-Security-Policy instead.

  Referrer-Policy: strict-origin-when-cross-origin
    Controls how much referrer information the browser includes on navigation.

  Permissions-Policy: camera=(), microphone=()
    Restricts access to device features. Geolocation is intentionally not
    restricted here because the mobile app legitimately uses it.

Headers applied in PRODUCTION only:
  Strict-Transport-Security: max-age=31536000; includeSubDomains
    Tells browsers to only reach this origin over HTTPS for the next year.
    Only meaningful when the service is served over TLS — enforcing it in
    local dev would break plain-HTTP connections.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_ALWAYS_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=()",
}

_PRODUCTION_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects security headers into every outgoing response.

    Production-only headers are enabled when APP_ENV=production. The check
    reads settings lazily to avoid a circular import at module load time.
    """

    def __init__(self, app: object, production: bool = False) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._production = production

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        for name, value in _ALWAYS_HEADERS.items():
            response.headers[name] = value

        if self._production:
            for name, value in _PRODUCTION_HEADERS.items():
                response.headers[name] = value

        return response
