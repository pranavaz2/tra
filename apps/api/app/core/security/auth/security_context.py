"""
SecurityContext — single immutable object carrying the complete security
state of one authenticated HTTP request.

Merges RequestContext (tracing, transport metadata) with AuthorizationContext
(verified identity, token metadata) into a single injectable object. Route
handlers that need both tracing IDs and the authenticated identity can depend
on SecurityContext instead of importing two separate dependencies.

Usage (authenticated routes):
    from app.core.security.auth.security_context import CurrentSecurityContext

    @router.get("/trips")
    async def list_trips(ctx: CurrentSecurityContext) -> Response:
        logger.info("Listing trips", extra={"request_id": ctx.request_id,
                                             "user_id": ctx.user_id})

Future-ready fields:
    device_trust_level  — populated by risk assessment (TASK-3.x).
                          Currently always "unknown" (no risk engine).
    risk_score          — 0.0–1.0 normalised risk score (TASK-3.x).
                          Currently always 0.0.

Design constraints:
    - This module must NOT import from app.modules.*. It is core infrastructure
      shared across all feature modules. Feature module presentation types
      (RequestContext) are intentionally not imported here; request fields are
      extracted from the raw FastAPI Request object in get_security_context().
    - All IDs are plain strings. No domain value objects here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Request

from app.core.middleware.request_id import get_correlation_id, get_request_id
from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import RequireAuthentication


@dataclass(frozen=True)
class SecurityContext:
    """
    Merged immutable snapshot of request and authentication state.

    Exposes every field from RequestContext and AuthorizationContext as
    a flat, directly-accessible surface. Route handlers receive one object
    instead of two separate dependencies.

    Tracing / Transport fields (extracted from FastAPI Request):
        request_id:     Unique ID for this HTTP request. Echoed in X-Request-ID.
        correlation_id: Links async background work to the originating request.
        ip_address:     Real client IP (X-Forwarded-For → X-Real-IP → REMOTE_ADDR).
        user_agent:     HTTP User-Agent header value.
        locale:         IETF BCP-47 language tag (Accept-Language header).
        timezone:       IANA timezone name (X-Timezone header).
        app_version:    Client app version string (X-App-Version header).
        received_at:    Server-side timestamp captured at dependency resolution time.

    Identity / Token fields (from AuthorizationContext):
        user_id:               UUID string of the authenticated user.
        session_id:            UUID string of the active session.
        token_id:              UUID string of the access token (JTI).
        token_version:         Monotonic counter; increment to invalidate all user tokens.
        session_version:       Monotonic counter; increment to invalidate this session.
        authentication_method: How the user authenticated ("password", "google", etc.).
        issued_at:             UTC datetime when the access token was issued.
        expires_at:            UTC datetime when the access token expires.
        email:                 Email address at token issuance.
        is_email_verified:     Whether the email was verified at token issuance.

    Future extension fields:
        device_trust_level: Inferred trust of the requesting device (TASK-3.x).
                            One of "unknown", "new", "trusted", "suspicious".
        risk_score:         Normalised 0.0–1.0 risk score from RiskAssessmentService.
                            0.0 = no risk; 1.0 = highest risk. Always 0.0 until TASK-3.x.
    """

    # ── Tracing / transport ──────────────────────────────────────────────────
    request_id: str
    correlation_id: str
    ip_address: str | None
    user_agent: str | None
    locale: str | None
    timezone: str | None
    app_version: str | None
    received_at: datetime

    # ── Identity / token ─────────────────────────────────────────────────────
    user_id: str
    session_id: str
    token_id: str
    token_version: int
    session_version: int
    authentication_method: str
    issued_at: datetime
    expires_at: datetime
    email: str
    is_email_verified: bool

    # ── Future risk / device signals ─────────────────────────────────────────
    device_trust_level: str = "unknown"   # DeviceTrust string (no domain import here)
    risk_score: float = 0.0


def _extract_client_ip(request: Request) -> str | None:
    """Extract the real client IP using X-Forwarded-For → X-Real-IP → REMOTE_ADDR."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return None


def build_security_context(
    auth_context: AuthorizationContext,
    *,
    request_id: str,
    correlation_id: str,
    ip_address: str | None,
    user_agent: str | None,
    locale: str | None,
    timezone: str | None,
    app_version: str | None,
    received_at: datetime,
    device_trust_level: str = "unknown",
    risk_score: float = 0.0,
) -> SecurityContext:
    """
    Build a SecurityContext from an AuthorizationContext and explicit request fields.

    Used in tests and any context where a full FastAPI Request object is not available.
    In normal route handling, use get_security_context() (the FastAPI dependency) instead.

    Args:
        auth_context:       Verified identity context from the Bearer token.
        request_id:         Unique request ID (from X-Request-ID or generated UUID).
        correlation_id:     Async correlation ID (from X-Correlation-ID or empty).
        ip_address:         Real client IP or None.
        user_agent:         HTTP User-Agent value or None.
        locale:             Accept-Language value or None.
        timezone:           X-Timezone value or None.
        app_version:        X-App-Version value or None.
        received_at:        Timestamp when the context was resolved.
        device_trust_level: DeviceTrust string (TASK-3.x).
        risk_score:         Risk score 0.0–1.0 (TASK-3.x).
    """
    return SecurityContext(
        request_id=request_id,
        correlation_id=correlation_id,
        ip_address=ip_address,
        user_agent=user_agent,
        locale=locale,
        timezone=timezone,
        app_version=app_version,
        received_at=received_at,
        user_id=auth_context.user_id,
        session_id=auth_context.session_id,
        token_id=auth_context.token_id,
        token_version=auth_context.token_version,
        session_version=auth_context.session_version,
        authentication_method=auth_context.authentication_method,
        issued_at=auth_context.issued_at,
        expires_at=auth_context.expires_at,
        email=auth_context.email,
        is_email_verified=auth_context.is_email_verified,
        device_trust_level=device_trust_level,
        risk_score=risk_score,
    )


async def get_security_context(
    request: Request,
    auth: RequireAuthentication,
) -> SecurityContext:
    """
    FastAPI dependency: build a SecurityContext for an authenticated request.

    Resolves RequireAuthentication (validates the Bearer token), extracts
    transport metadata from the raw Request, and merges them into a single
    SecurityContext. This dependency requires a valid Bearer token.

    Use CurrentSecurityContext in route handlers instead of this function directly.

    Raises:
        AuthorizationError: if the Bearer token is missing, malformed, expired,
                            invalid, or revoked.
    """
    return build_security_context(
        auth,
        request_id=get_request_id() or str(uuid.uuid4()),
        correlation_id=get_correlation_id(),
        ip_address=_extract_client_ip(request),
        user_agent=request.headers.get("User-Agent"),
        locale=request.headers.get("Accept-Language"),
        timezone=request.headers.get("X-Timezone"),
        app_version=request.headers.get("X-App-Version"),
        received_at=datetime.now(UTC),
    )


CurrentSecurityContext = Annotated[SecurityContext, Depends(get_security_context)]
"""
Typed FastAPI dependency for the merged security context (authenticated routes).

Declares that the route requires a valid Bearer token. Resolves to a SecurityContext
providing both tracing IDs and verified identity in a single flat object.

Usage::

    from app.core.security.auth.security_context import CurrentSecurityContext

    @router.get("/trips")
    async def list_trips(ctx: CurrentSecurityContext) -> Response:
        user_id = ctx.user_id        # from auth token
        request_id = ctx.request_id  # from request middleware
"""
