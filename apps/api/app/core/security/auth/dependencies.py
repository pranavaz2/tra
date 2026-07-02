"""
FastAPI dependency providers for authorization.

All protected routes depend on RequireAuthentication (or a derived type).
Public routes simply omit the dependency. Optional-auth routes depend on
OptionalAuthentication, which returns None when no token is present.

Token validation pipeline (get_authorization_context):
  1. Extract Authorization header
  2. Validate "Bearer " prefix (RFC 6750)
  3. JWTService.verify_access_token() — structure, signature, exp, iss, aud, claims
  4. TokenRevocationChecker.is_revoked() — Redis JTI blacklist (placeholder: always False)
  5. Build and return AuthorizationContext

Error responses follow RFC 7807 via AuthorizationError (handled in app.main).

Logging policy (CLAUDE.md §11 — never log):
  - JWT string
  - Authorization header value
  - Token hash or claims payload
Safe to log: request_id, user_id, session_id, token_id (JTI), outcome.

Extension points:
  - require_role(role)       → future RBAC dependency (wraps RequireAuthentication)
  - require_permission(perm) → future ABAC dependency
  - RedisTokenRevocationChecker → swap via get_token_revocation_checker() override
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.errors import AuthorizationError
from app.core.security.auth.revocation import NullTokenRevocationChecker
from app.core.security.jwt.claims import DecodedAccessToken
from app.core.security.jwt.dependencies import CurrentJWTService
from app.core.security.jwt.errors import JWTExpiredError, JWTError
from app.core.security.jwt.interfaces import JWTService, TokenRevocationChecker

logger = logging.getLogger(__name__)

_BEARER_PREFIX = "Bearer "
_BEARER_PREFIX_LEN = len(_BEARER_PREFIX)

# ──────────────────────────────────────────────────────────────────────────── #
# Token revocation checker                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


@lru_cache(maxsize=1)
def _build_revocation_checker() -> NullTokenRevocationChecker:
    return NullTokenRevocationChecker()


def get_token_revocation_checker() -> TokenRevocationChecker:
    """
    Return the active token revocation checker.

    Currently returns NullTokenRevocationChecker (always non-revoked).
    TASK-2.12: replace with RedisTokenRevocationChecker(redis_client).

    Override in tests:
        app.dependency_overrides[get_token_revocation_checker] = lambda: StubRevocationChecker()
    """
    return _build_revocation_checker()


CurrentTokenRevocationChecker = Annotated[
    TokenRevocationChecker, Depends(get_token_revocation_checker)
]

# ──────────────────────────────────────────────────────────────────────────── #
# Bearer token extraction                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


def _extract_bearer_token(request: Request, *, trace_id: str) -> str:
    """
    Extract the raw JWT string from the Authorization header.

    Raises AuthorizationError for:
      - Missing Authorization header → AUTH_TOKEN_MISSING
      - Header present but not "Bearer <token>" format → AUTH_TOKEN_MALFORMED
      - "Bearer " prefix present but token value is empty → AUTH_TOKEN_MALFORMED

    Returns the raw token string (not decoded, not validated).
    """
    instance = request.url.path
    auth_header: str = request.headers.get("Authorization", "")

    if not auth_header:
        raise AuthorizationError.missing_token(trace_id=trace_id, instance=instance)

    if not auth_header.startswith(_BEARER_PREFIX):
        raise AuthorizationError.malformed_header(trace_id=trace_id, instance=instance)

    token = auth_header[_BEARER_PREFIX_LEN:]
    if not token:
        raise AuthorizationError.malformed_header(trace_id=trace_id, instance=instance)

    return token


# ──────────────────────────────────────────────────────────────────────────── #
# Core authorization dependency                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


async def get_authorization_context(
    request: Request,
    jwt_service: CurrentJWTService,
    revocation_checker: CurrentTokenRevocationChecker,
) -> AuthorizationContext:
    """
    Validate the Bearer token and return an AuthorizationContext.

    Raises AuthorizationError for every failure mode. The exception handler
    in app.main converts it to a JSONResponse with RFC 7807 body.

    Never raises for valid tokens — callers receive AuthorizationContext directly.

    Usage:
        RequireAuthentication = Annotated[AuthorizationContext, Depends(get_authorization_context)]

        @router.get("/trips")
        async def list_trips(auth: RequireAuthentication) -> ...:
            user_id = auth.user_id
    """
    trace_id = get_request_id() or ""
    instance = request.url.path

    # ── Step 1: Extract Bearer token ─────────────────────────────────────── #
    token = _extract_bearer_token(request, trace_id=trace_id)

    # ── Step 2: Validate JWT (structure, signature, exp, claims) ─────────── #
    try:
        decoded = jwt_service.verify_access_token(token)
    except JWTExpiredError:
        logger.info(
            "Authorization failed — token expired",
            extra={"request_id": trace_id, "path": instance},
        )
        raise AuthorizationError.expired_token(trace_id=trace_id, instance=instance)
    except JWTError:
        logger.info(
            "Authorization failed — invalid token",
            extra={"request_id": trace_id, "path": instance},
        )
        raise AuthorizationError.invalid_token(trace_id=trace_id, instance=instance)

    # ── Step 3: Check revocation blacklist ───────────────────────────────── #
    jti = decoded.claims.jti
    if await revocation_checker.is_revoked(jti):
        logger.info(
            "Authorization failed — token revoked",
            extra={
                "request_id": trace_id,
                "user_id": decoded.claims.user_id,
                "session_id": decoded.claims.session_id,
                "token_id": jti,
            },
        )
        raise AuthorizationError.revoked_token(trace_id=trace_id, instance=instance)

    # ── Step 4: Build authorization context ──────────────────────────────── #
    ctx = AuthorizationContext(
        user_id=decoded.claims.user_id,
        session_id=decoded.claims.session_id,
        token_id=jti,
        token_version=decoded.claims.token_version,
        session_version=decoded.claims.session_version,
        authentication_method=decoded.claims.authentication_method,
        issued_at=decoded.claims.iat,
        expires_at=decoded.claims.exp,
        email=decoded.claims.email,
        is_email_verified=decoded.claims.verified,
    )

    logger.info(
        "Authorization succeeded",
        extra={
            "request_id": trace_id,
            "user_id": ctx.user_id,
            "session_id": ctx.session_id,
        },
    )

    return ctx


# ──────────────────────────────────────────────────────────────────────────── #
# Optional authentication                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


async def get_optional_authorization_context(
    request: Request,
    jwt_service: CurrentJWTService,
    revocation_checker: CurrentTokenRevocationChecker,
) -> AuthorizationContext | None:
    """
    Like get_authorization_context but returns None when no token is present.

    Useful for routes that behave differently for authenticated vs anonymous
    visitors (e.g., public trip explorer with personalisation when logged in).

    Still validates and rejects malformed/expired/revoked tokens — only a
    completely absent Authorization header returns None without an error.

    Usage:
        OptionalAuthentication = Annotated[AuthorizationContext | None, Depends(...)]

        @router.get("/destinations/{id}")
        async def get_destination(auth: OptionalAuthentication) -> ...:
            if auth:
                # personalized response
            else:
                # anonymous response
    """
    auth_header: str = request.headers.get("Authorization", "")
    if not auth_header:
        return None

    return await get_authorization_context(
        request=request,
        jwt_service=jwt_service,
        revocation_checker=revocation_checker,
    )


# ──────────────────────────────────────────────────────────────────────────── #
# Public type aliases — import these in route handlers                           #
# ──────────────────────────────────────────────────────────────────────────── #

RequireAuthentication = Annotated[
    AuthorizationContext, Depends(get_authorization_context)
]
"""
Dependency that requires a valid Bearer token.

Routes that declare this dependency will return 401 if:
  - Authorization header is absent
  - Header is not in 'Bearer <token>' format
  - Token is expired, has invalid signature, or fails claim validation
  - Token has been revoked (TASK-2.12)

Usage::

    from app.core.security.auth.dependencies import RequireAuthentication

    @router.get("/trips")
    async def list_trips(auth: RequireAuthentication) -> Response:
        user_id = auth.user_id
        ...
"""

OptionalAuthentication = Annotated[
    AuthorizationContext | None, Depends(get_optional_authorization_context)
]
"""
Dependency that accepts but does not require a valid Bearer token.

Returns None when no Authorization header is present.
Still rejects malformed, expired, or revoked tokens with 401.

Usage::

    from app.core.security.auth.dependencies import OptionalAuthentication

    @router.get("/destinations/{id}")
    async def get_destination(auth: OptionalAuthentication) -> Response:
        if auth is not None:
            # personalise for auth.user_id
        ...
"""


# ──────────────────────────────────────────────────────────────────────────── #
# Derived fine-grained dependencies                                              #
# ──────────────────────────────────────────────────────────────────────────── #


async def get_current_user_id(auth: RequireAuthentication) -> str:
    """Return the authenticated user's ID (UUID string)."""
    return auth.user_id


async def get_current_session_id(auth: RequireAuthentication) -> str:
    """Return the authenticated session ID (UUID string)."""
    return auth.session_id


async def get_current_access_token(
    request: Request,
    jwt_service: CurrentJWTService,
    revocation_checker: CurrentTokenRevocationChecker,
) -> DecodedAccessToken:
    """
    Return the fully decoded and validated access token.

    Use when you need the raw decoded token (e.g., for logout flows that
    extract the JTI for revocation). Most routes should use RequireAuthentication
    (AuthorizationContext) instead — it provides higher-level field access.
    """
    trace_id = get_request_id() or ""
    instance = request.url.path
    token = _extract_bearer_token(request, trace_id=trace_id)

    try:
        decoded = jwt_service.verify_access_token(token)
    except JWTExpiredError:
        raise AuthorizationError.expired_token(trace_id=trace_id, instance=instance)
    except JWTError:
        raise AuthorizationError.invalid_token(trace_id=trace_id, instance=instance)

    if await revocation_checker.is_revoked(decoded.claims.jti):
        raise AuthorizationError.revoked_token(trace_id=trace_id, instance=instance)

    return decoded


CurrentAuthorizationContext = Annotated[
    AuthorizationContext, Depends(get_authorization_context)
]
"""Alias for RequireAuthentication. Use RequireAuthentication in new code."""

CurrentUser = Annotated[str, Depends(get_current_user_id)]
"""Authenticated user ID (UUID string). Requires valid Bearer token."""

CurrentSession = Annotated[str, Depends(get_current_session_id)]
"""Authenticated session ID (UUID string). Requires valid Bearer token."""

CurrentAccessToken = Annotated[DecodedAccessToken, Depends(get_current_access_token)]
"""
Fully decoded access token. Use for logout/revocation flows.
Most routes should use RequireAuthentication (AuthorizationContext) instead.
"""
