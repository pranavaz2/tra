"""
RFC 7807 error responses for the authorization middleware.

AuthorizationError is raised by auth dependencies and handled by
authorization_error_handler() registered in app.main.create_app().

Error type URI convention (matches the authentication module):
  https://errors.travix.ai/auth/<kebab-case-slug>

All responses carry:
  - WWW-Authenticate: Bearer    (RFC 6750 §3)
  - trace_id from the request ContextVar

Security:
  - No JWT, token, or signature material appears in any response.
  - Error detail messages are generic — they do not reveal whether
    the email exists, whether the token was structurally valid, etc.
  - The only distinguishable error codes are those the client must act on:
      AUTH_TOKEN_MISSING    → prompt login
      AUTH_TOKEN_MALFORMED  → prompt login (bad client implementation)
      AUTH_TOKEN_EXPIRED    → attempt silent refresh
      AUTH_TOKEN_INVALID    → prompt login
      AUTH_TOKEN_REVOKED    → prompt login
"""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

_AUTH_ERROR_BASE = "https://errors.travix.ai/auth"
_WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}


def _auth_problem(
    *,
    slug: str,
    title: str,
    http_status: int,
    detail: str,
    error_code: str,
    trace_id: str,
    instance: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an RFC 7807 Problem Details body for auth middleware errors."""
    body: dict[str, Any] = {
        "type": f"{_AUTH_ERROR_BASE}/{slug}",
        "title": title,
        "status": http_status,
        "detail": detail,
        "instance": instance,
        "error_code": error_code,
        "trace_id": trace_id,
    }
    if extra:
        body.update(extra)
    return body


class AuthorizationError(Exception):
    """
    Raised by auth dependencies when a request cannot be authorized.

    Contains a pre-built RFC 7807 response body and the HTTP status code.
    Converted to JSONResponse by authorization_error_handler() in app.main.

    Never catch this in route handlers — let it propagate to the handler.
    Use the class methods to construct typed instances.
    """

    def __init__(self, *, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self.body = body

    def to_response(self) -> JSONResponse:
        """Convert to a JSONResponse with WWW-Authenticate header."""
        return JSONResponse(
            status_code=self.status_code,
            content=self.body,
            headers=_WWW_AUTHENTICATE,
        )

    # ── Named constructors ─────────────────────────────────────────────────── #

    @classmethod
    def missing_token(cls, *, trace_id: str, instance: str) -> "AuthorizationError":
        """No Authorization header present."""
        return cls(
            status_code=status.HTTP_401_UNAUTHORIZED,
            body=_auth_problem(
                slug="token-missing",
                title="Unauthorized",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required. Provide a Bearer token.",
                error_code="AUTH_TOKEN_MISSING",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    @classmethod
    def malformed_header(cls, *, trace_id: str, instance: str) -> "AuthorizationError":
        """Authorization header present but not in 'Bearer <token>' format."""
        return cls(
            status_code=status.HTTP_401_UNAUTHORIZED,
            body=_auth_problem(
                slug="token-malformed",
                title="Unauthorized",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed Authorization header. Expected: Bearer <token>.",
                error_code="AUTH_TOKEN_MALFORMED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    @classmethod
    def expired_token(cls, *, trace_id: str, instance: str) -> "AuthorizationError":
        """Token is structurally valid but has passed its exp claim."""
        return cls(
            status_code=status.HTTP_401_UNAUTHORIZED,
            body=_auth_problem(
                slug="token-expired",
                title="Unauthorized",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has expired. Refresh using your refresh token.",
                error_code="AUTH_TOKEN_EXPIRED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    @classmethod
    def invalid_token(cls, *, trace_id: str, instance: str) -> "AuthorizationError":
        """Token fails signature, issuer, audience, or claim validation."""
        return cls(
            status_code=status.HTTP_401_UNAUTHORIZED,
            body=_auth_problem(
                slug="token-invalid",
                title="Unauthorized",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Token is invalid. Please log in again.",
                error_code="AUTH_TOKEN_INVALID",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    @classmethod
    def revoked_token(cls, *, trace_id: str, instance: str) -> "AuthorizationError":
        """Token JTI is in the revocation blacklist."""
        return cls(
            status_code=status.HTTP_401_UNAUTHORIZED,
            body=_auth_problem(
                slug="token-revoked",
                title="Unauthorized",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked. Please log in again.",
                error_code="AUTH_TOKEN_REVOKED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    @classmethod
    def insufficient_permissions(
        cls, *, trace_id: str, instance: str
    ) -> "AuthorizationError":
        """
        Extension point for future RBAC: caller lacks required role/permission.

        Not yet raised — no roles are checked in TASK-2.11.
        Reserved for future require_role() / require_permission() decorators.
        """
        return cls(
            status_code=status.HTTP_403_FORBIDDEN,
            body=_auth_problem(
                slug="insufficient-permissions",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
                error_code="AUTH_INSUFFICIENT_PERMISSIONS",
                trace_id=trace_id,
                instance=instance,
            ),
        )
