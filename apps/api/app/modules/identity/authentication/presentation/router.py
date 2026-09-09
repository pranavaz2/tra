"""
Authentication Presentation Layer — FastAPI Router.

Implements:
  POST /api/v1/auth/register  — Authentication API Contract §5.1
  POST /api/v1/auth/login     — Authentication API Contract §5.2

Responsibility (per endpoint):
  1. Receive the validated Pydantic request body (transport validation only).
  2. Extract RequestContext (trace IDs, client IP, user_agent, timestamps).
  3. Build the appropriate command and call the application service.
  4. Map the Result[T] to a JSON HTTP response.
  5. Return the response with the X-Request-ID header.

What this router does NOT do:
  - Business validation (no email format check, no strength rules)
  - Persistence (no direct repository access)
  - Infrastructure logic (no Redis, no DB session)
  - Raising HTTPException (all error paths build JSONResponse via error_responses)

Rate limiting:
  Both endpoints are subject to per-IP rate limits per the API contract.
  Implementation is deferred to a Redis-backed rate limiting middleware (TASK-2.11).
  The RateLimitInfo and add_rate_limit_headers() extension points in
  error_responses.py are the planned integration surface.

Idempotency:
  The Idempotency-Key header (UUID v4) is read and echoed in the response but
  NOT persisted yet. Future implementation: store (ip, key) → response body
  in Redis DB 3 with a 24-hour TTL and return the stored body on repeat requests.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, Response

from app.config import get_settings
from app.core.security.auth.dependencies import RequireAuthentication
from app.core.security.jwt.claims import AccessTokenClaims
from app.core.security.jwt.dependencies import CurrentJWTService
from app.modules.identity.authentication.application.commands import (
    LoginUserCommand,
    RegisterUserCommand,
)
from app.modules.identity.authentication.domain.errors import (
    AccountDisabledError,
    RefreshTokenNotFoundError,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.infrastructure.dependencies import (
    CurrentAuthRepository,
    CurrentLoginService,
    CurrentRefreshTokenService,
    CurrentRefreshTokenStore,
    CurrentRegistrationService,
    CurrentSessionRepository,
)
from app.modules.identity.authentication.presentation.error_responses import (
    map_login_failure,
    map_refresh_failure,
    map_registration_failure,
)
from app.modules.identity.authentication.presentation.request_context import (
    CurrentRequestContext,
    RequestContext,
)
from app.modules.identity.authentication.presentation.schemas import (
    DataEnvelope,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SessionResponse,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_REGISTER_PATH = "/api/v1/auth/register"
_LOGIN_PATH = "/api/v1/auth/login"
_REFRESH_PATH = "/api/v1/auth/refresh"
_LOGOUT_PATH = "/api/v1/auth/logout"

# Idempotency-Key header name (extension point — not yet persisted)
_IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


@router.post(
    "/register",
    status_code=201,
    summary="Register a new user account",
    operation_id="registerUser",
    response_description="User account created successfully.",
    description="""
Create a new user account with email and password credentials.

## Production behaviour (`requires_verification: true`)

- Account is created in an **unverified** state.
- No tokens are issued.
- A verification email is dispatched asynchronously.
- The client should display a "check your email" screen.
- The user logs in after completing `POST /verify-email`.

## Development / CI behaviour (`requires_verification: false`)

- Email verification is **bypassed** via server configuration only.
  The client cannot influence this — it is controlled by the server.
- Tokens are issued immediately (same shape as the login response).
- The client should navigate to the home screen using the returned tokens.

## Client integration notes

- Inspect `requires_verification` before navigating after a 201 response.
- Display `email` from the response body (server-normalised), not the raw user input.
- The `violations` array inside `AUTH_PASSWORD_TOO_WEAK` maps directly to inline form errors.
- Store the `refresh_token` in Flutter Secure Storage. Keep `access_token` in memory only.

## Rate limiting

- **5 requests per hour per IP address** (not yet enforced — planned).
- The `X-RateLimit-*` headers will be present on all responses once implemented.
- A `Retry-After` header will accompany 429 responses.

## Idempotency

- An `Idempotency-Key` header (UUID v4) is accepted and echoed in responses.
- Persistence of idempotency records is not yet implemented.
  When implemented: repeat requests with the same key within 24 hours will
  return the stored response without re-executing registration.
""",
    responses={
        201: {
            "description": "Registration successful.",
            "content": {
                "application/json": {
                    "examples": {
                        "verification_required": {
                            "summary": "Production — email verification required",
                            "description": (
                                "Default production response. The user must verify "
                                "their email via POST /verify-email before logging in."
                            ),
                            "value": {
                                "data": {
                                    "user_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                                    "email": "alice@example.com",
                                    "requires_verification": True,
                                    "message": (
                                        "Please check your email to verify your "
                                        "account before logging in."
                                    ),
                                }
                            },
                        },
                        "auto_login": {
                            "summary": "Dev / CI — auto-verified, tokens issued",
                            "description": (
                                "Returned only when the server has auto-verify enabled "
                                "(REGISTRATION_AUTO_VERIFY_EMAIL=true). Never in production."
                            ),
                            "value": {
                                "data": {
                                    "user_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                                    "email": "alice@example.com",
                                    "requires_verification": False,
                                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                                    "refresh_token": "8f14e45f-ceea-467a-a866-051f0ee75a5e",
                                    "token_type": "Bearer",
                                    "access_token_expires_at": "2026-06-27T00:15:00Z",
                                    "refresh_token_expires_at": "2026-07-04T00:00:00Z",
                                    "session": {
                                        "session_id": "c4d7e9f0-1b2a-3c4d-5e6f-7a8b9c0d1e2f",
                                        "device_name": None,
                                        "created_at": "2026-06-27T00:00:00Z",
                                    },
                                }
                            },
                        },
                    }
                }
            },
        },
        409: {
            "description": "Email already registered.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/email-already-exists",
                        "title": "Email Already Exists",
                        "status": 409,
                        "detail": (
                            "An account with this email address already exists."
                        ),
                        "instance": "/api/v1/auth/register",
                        "error_code": "AUTH_EMAIL_ALREADY_EXISTS",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        422: {
            "description": "Email format invalid or password too weak.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_email": {
                            "summary": "Email address is invalid",
                            "value": {
                                "type": "https://errors.travix.ai/validation-error",
                                "title": "Validation Error",
                                "status": 422,
                                "detail": "One or more fields failed validation.",
                                "instance": "/api/v1/auth/register",
                                "error_code": "VALIDATION_ERROR",
                                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                                "errors": [
                                    {
                                        "field": "email",
                                        "error_code": "AUTH_EMAIL_INVALID",
                                        "message": "Enter a valid email address.",
                                    }
                                ],
                            },
                        },
                        "weak_password": {
                            "summary": "Password does not meet strength requirements",
                            "value": {
                                "type": "https://errors.travix.ai/validation-error",
                                "title": "Validation Error",
                                "status": 422,
                                "detail": "One or more fields failed validation.",
                                "instance": "/api/v1/auth/register",
                                "error_code": "VALIDATION_ERROR",
                                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                                "errors": [
                                    {
                                        "field": "password",
                                        "error_code": "AUTH_PASSWORD_TOO_WEAK",
                                        "message": (
                                            "Password does not meet strength requirements."
                                        ),
                                        "violations": [
                                            "Must be at least 12 characters"
                                        ],
                                    }
                                ],
                            },
                        },
                        "transport_validation": {
                            "summary": "Transport-level validation failure (Pydantic)",
                            "description": (
                                "Returned by FastAPI before the handler is called "
                                "when the request body cannot be parsed (e.g., "
                                "missing required fields, field too long)."
                            ),
                            "value": {
                                "type": "https://errors.travix.ai/validation-error",
                                "title": "Validation Error",
                                "status": 422,
                                "detail": "One or more fields failed validation.",
                                "instance": "/api/v1/auth/register",
                                "error_code": "VALIDATION_ERROR",
                                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                                "errors": [
                                    {
                                        "field": "email",
                                        "error_code": "AUTH_EMAIL_INVALID",
                                        "message": "Enter a valid email address.",
                                    }
                                ],
                            },
                        },
                    }
                }
            },
        },
        429: {
            "description": (
                "Rate limit exceeded. 5 requests per hour per IP address."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/rate-limited",
                        "title": "Too Many Requests",
                        "status": 429,
                        "detail": (
                            "Too many registration attempts. Try again in 3600 seconds."
                        ),
                        "instance": "/api/v1/auth/register",
                        "error_code": "AUTH_RATE_LIMITED",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                        "retry_after_seconds": 3600,
                    }
                }
            },
        },
        500: {
            "description": "Unexpected internal error.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/internal-server-error",
                        "title": "Internal Server Error",
                        "status": 500,
                        "detail": (
                            "An unexpected error occurred. Please try again later."
                        ),
                        "instance": "/api/v1/auth/register",
                        "error_code": "AUTH_INTERNAL_ERROR",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        503: {
            "description": "Service temporarily unavailable (hashing or DB failure).",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/service-unavailable",
                        "title": "Service Unavailable",
                        "status": 503,
                        "detail": (
                            "Registration is temporarily unavailable. "
                            "Please try again shortly."
                        ),
                        "instance": "/api/v1/auth/register",
                        "error_code": "AUTH_SERVICE_UNAVAILABLE",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
    },
)
async def register_user(
    body: RegisterRequest,
    ctx: CurrentRequestContext,
    registration: CurrentRegistrationService,
) -> Response:
    """
    POST /api/v1/auth/register — Route handler.

    Translation-only. Receives validated Pydantic body → builds command →
    calls service → maps result to HTTP response. Zero business logic.
    """
    logger.info(
        "Registration request",
        extra={
            "request_id": ctx.request_id,
            "ip_address": ctx.ip_address,
            "user_agent": ctx.user_agent,
        },
    )

    # ── Build command from request ────────────────────────────────────────── #

    command = RegisterUserCommand(
        email=body.email,
        password=body.password,
        device_id=None,
        device_name=body.device_info.device_name if body.device_info else None,
        platform=body.device_info.platform if body.device_info else None,
        create_session=True,
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
    )

    # ── Execute ───────────────────────────────────────────────────────────── #

    result = await registration.execute(command)

    # ── Map failure ───────────────────────────────────────────────────────── #

    if not result.is_ok:
        logger.info(
            "Registration failed",
            extra={
                "request_id": ctx.request_id,
                "error_code": result.error.code,
            },
        )
        return map_registration_failure(
            result.error,
            trace_id=ctx.request_id,
            instance=_REGISTER_PATH,
        )

    # ── Build success response ────────────────────────────────────────────── #

    summary = result.value
    settings = get_settings()

    response_headers = {"X-Request-ID": ctx.request_id}

    if summary.requires_email_verification:
        # Production path: no tokens; user must verify email
        response_data = RegisterResponse(
            user_id=str(summary.user_id),
            email=str(summary.email),
            requires_verification=True,
            message=(
                "Please check your email to verify your account before logging in."
            ),
        )
    else:
        # Dev/CI path: email auto-verified; tokens issued immediately
        access_expires_at = ctx.received_at + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
        refresh_expires_at = ctx.received_at + timedelta(
            days=settings.jwt_refresh_token_expire_days
        )

        session_info: SessionResponse | None = None
        if summary.session_id is not None:
            session_info = SessionResponse(
                session_id=str(summary.session_id),
                # device_name comes from the original request — not in RegistrationSummary
                device_name=(
                    body.device_info.device_name if body.device_info else None
                ),
                created_at=ctx.received_at,
            )

        # plain_refresh_token.as_client_token() is the only safe extraction path.
        # Never call str() or repr() — both return [REDACTED].
        raw_refresh_token: str | None = (
            summary.plain_refresh_token.as_client_token()
            if summary.plain_refresh_token is not None
            else None
        )

        response_data = RegisterResponse(
            user_id=str(summary.user_id),
            email=str(summary.email),
            requires_verification=False,
            access_token=summary.access_token,
            refresh_token=raw_refresh_token,
            token_type="Bearer",
            access_token_expires_at=access_expires_at,
            refresh_token_expires_at=refresh_expires_at,
            session=session_info,
        )

    logger.info(
        "Registration succeeded",
        extra={
            "request_id": ctx.request_id,
            "requires_verification": summary.requires_email_verification,
            "session_created": summary.session_created,
        },
    )

    return JSONResponse(
        status_code=201,
        content=DataEnvelope(data=response_data).model_dump(mode="json"),
        headers=response_headers,
    )


@router.post(
    "/login",
    status_code=200,
    summary="Authenticate with email and password",
    operation_id="loginUser",
    response_description="Authentication successful. Tokens issued.",
    description="""
Authenticate a registered user with email and password credentials.

## On success (200)

- An `access_token` (JWT, 15-minute lifetime) and `refresh_token` (7-day lifetime)
  are issued.
- Store the `refresh_token` in Flutter Secure Storage. Keep `access_token` in memory
  only — never persist it.
- Replace both tokens on every successful `POST /refresh` call.
- Use `access_token_expires_at` to proactively refresh the access token before expiry.

## Rate limiting

- **10 requests per minute per IP address** (not yet enforced — planned).
- **5 attempts per hour per account** (not yet enforced — planned).
- The `X-RateLimit-*` headers will be present on all responses once implemented.
- A `Retry-After` header will accompany 429 and 423 responses.

## Account lockout

- After repeated failed login attempts, the account is temporarily locked.
- A `423 Locked` response is returned with a `Retry-After` header indicating
  when the account will be unlocked.
- The `locked_until` field in the response body provides the exact unlock timestamp.

## Email verification

- If the server requires email verification (`registration_require_email_verification`),
  login is blocked for unverified accounts.
- A `403 Forbidden` response with `error_code: AUTH_EMAIL_NOT_VERIFIED` is returned.
- The user must complete `POST /verify-email` before logging in.
""",
    responses={
        200: {
            "description": "Authentication successful. Access and refresh tokens issued.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                            "refresh_token": "8f14e45f-ceea-467a-a866-051f0ee75a5e",
                            "token_type": "Bearer",
                            "access_token_expires_at": "2026-07-01T12:15:00Z",
                            "refresh_token_expires_at": "2026-07-08T12:00:00Z",
                            "session": {
                                "session_id": "c4d7e9f0-1b2a-3c4d-5e6f-7a8b9c0d1e2f",
                                "device_name": "Alice's iPhone 15 Pro",
                                "created_at": "2026-07-01T12:00:00Z",
                            },
                            "user": {
                                "user_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                                "email": "alice@example.com",
                                "is_email_verified": True,
                            },
                        }
                    }
                }
            },
        },
        401: {
            "description": "Invalid email or password.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/invalid-credentials",
                        "title": "Invalid Credentials",
                        "status": 401,
                        "detail": "Email or password is incorrect.",
                        "instance": "/api/v1/auth/login",
                        "error_code": "AUTH_INVALID_CREDENTIALS",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        403: {
            "description": "Account disabled or email not verified.",
            "content": {
                "application/json": {
                    "examples": {
                        "email_not_verified": {
                            "summary": "Email not yet verified",
                            "value": {
                                "type": "https://errors.travix.ai/auth/email-not-verified",
                                "title": "Email Not Verified",
                                "status": 403,
                                "detail": (
                                    "Please verify your email address before logging in."
                                ),
                                "instance": "/api/v1/auth/login",
                                "error_code": "AUTH_EMAIL_NOT_VERIFIED",
                                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                            },
                        },
                        "account_disabled": {
                            "summary": "Account permanently disabled",
                            "value": {
                                "type": "https://errors.travix.ai/auth/account-disabled",
                                "title": "Account Disabled",
                                "status": 403,
                                "detail": (
                                    "This account has been disabled. "
                                    "Please contact support."
                                ),
                                "instance": "/api/v1/auth/login",
                                "error_code": "AUTH_ACCOUNT_DISABLED",
                                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                            },
                        },
                    }
                }
            },
        },
        422: {
            "description": "Request body failed transport validation.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/validation-error",
                        "title": "Validation Error",
                        "status": 422,
                        "detail": "One or more fields failed validation.",
                        "instance": "/api/v1/auth/login",
                        "error_code": "VALIDATION_ERROR",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                        "errors": [
                            {
                                "field": "email",
                                "error_code": "AUTH_EMAIL_INVALID",
                                "message": "Enter a valid email address.",
                            }
                        ],
                    }
                }
            },
        },
        423: {
            "description": (
                "Account temporarily locked after repeated failed login attempts."
            ),
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/account-locked",
                        "title": "Account Locked",
                        "status": 423,
                        "detail": (
                            "This account is temporarily locked. "
                            "Please try again in 15 minute(s)."
                        ),
                        "instance": "/api/v1/auth/login",
                        "error_code": "AUTH_ACCOUNT_LOCKED",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                        "locked_until": "2026-07-01T12:15:00Z",
                        "retry_after_seconds": 900,
                    }
                }
            },
        },
        429: {
            "description": "Rate limit exceeded.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/rate-limited",
                        "title": "Too Many Requests",
                        "status": 429,
                        "detail": (
                            "Too many login attempts. Try again in 60 seconds."
                        ),
                        "instance": "/api/v1/auth/login",
                        "error_code": "AUTH_RATE_LIMITED",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                        "retry_after_seconds": 60,
                    }
                }
            },
        },
        500: {
            "description": "Unexpected internal error.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/internal-server-error",
                        "title": "Internal Server Error",
                        "status": 500,
                        "detail": "An unexpected error occurred. Please try again later.",
                        "instance": "/api/v1/auth/login",
                        "error_code": "AUTH_INTERNAL_ERROR",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        503: {
            "description": "Service temporarily unavailable.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/auth/service-unavailable",
                        "title": "Service Unavailable",
                        "status": 503,
                        "detail": (
                            "Login is temporarily unavailable. "
                            "Please try again shortly."
                        ),
                        "instance": "/api/v1/auth/login",
                        "error_code": "AUTH_SERVICE_UNAVAILABLE",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
    },
)
async def login_user(
    body: LoginRequest,
    ctx: CurrentRequestContext,
    login_service: CurrentLoginService,
) -> Response:
    """
    POST /api/v1/auth/login — Route handler.

    Translation-only. Receives validated Pydantic body → builds command →
    calls service → maps result to HTTP response. Zero business logic.
    """
    logger.info(
        "Login request",
        extra={
            "request_id": ctx.request_id,
            "ip_address": ctx.ip_address,
            "user_agent": ctx.user_agent,
        },
    )

    # ── Build command from request ────────────────────────────────────────── #

    command = LoginUserCommand(
        email=body.email,
        password=body.password,
        device_id=None,
        device_name=body.device_info.device_name if body.device_info else None,
        platform=body.device_info.platform if body.device_info else None,
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
    )

    # ── Execute ───────────────────────────────────────────────────────────── #

    result = await login_service.execute(command)

    # ── Map failure ───────────────────────────────────────────────────────── #

    if not result.is_ok:
        logger.info(
            "Login failed",
            extra={
                "request_id": ctx.request_id,
                "error_code": result.error.code,
            },
        )
        return map_login_failure(
            result.error,
            trace_id=ctx.request_id,
            instance=_LOGIN_PATH,
        )

    # ── Build success response ────────────────────────────────────────────── #

    summary = result.value

    # plain_refresh_token.as_client_token() is the only safe extraction path.
    # Never call str() or repr() — both return [REDACTED].
    raw_refresh_token: str = summary.plain_refresh_token.as_client_token()

    session_response = SessionResponse(
        session_id=str(summary.session_id),
        device_name=body.device_info.device_name if body.device_info else None,
        created_at=ctx.received_at,
    )

    user_response = UserResponse(
        user_id=str(summary.user_id),
        email=str(summary.email),
        is_email_verified=summary.is_email_verified,
    )

    response_data = LoginResponse(
        access_token=summary.access_token,
        refresh_token=raw_refresh_token,
        token_type="Bearer",
        access_token_expires_at=summary.access_token_expires_at,
        refresh_token_expires_at=summary.refresh_token_expires_at,
        session=session_response,
        user=user_response,
    )

    logger.info(
        "Login succeeded",
        extra={
            "request_id": ctx.request_id,
            "user_id": str(summary.user_id),
            "session_id": str(summary.session_id),
        },
    )

    return JSONResponse(
        status_code=200,
        content=DataEnvelope(data=response_data).model_dump(mode="json"),
        headers={"X-Request-ID": ctx.request_id},
    )


@router.post(
    "/refresh",
    status_code=200,
    summary="Refresh access token",
    operation_id="refreshToken",
    response_description="Tokens rotated successfully.",
    response_model=DataEnvelope[LoginResponse],
)
async def refresh(
    body: RefreshRequest,
    refresh_token_service: CurrentRefreshTokenService,
    token_store: CurrentRefreshTokenStore,
    auth_repo: CurrentAuthRepository,
    jwt_service: CurrentJWTService,
    ctx: CurrentRequestContext,
) -> Response:
    """
    Exchange a valid refresh token for a new access token and rotated refresh token.
    """
    result = await refresh_token_service.rotate(
        presented_token=body.refresh_token,
    )

    if not result.is_ok:
        logger.info(
            "Refresh failed",
            extra={"request_id": ctx.request_id, "error_code": result.error.code},
        )
        return map_refresh_failure(
            result.error,
            trace_id=ctx.request_id,
            instance=_REFRESH_PATH,
        )

    new_plain_token, new_record_id = result.value
    new_record = await token_store.find_by_id(new_record_id)
    if new_record is None:
        return map_refresh_failure(
            RefreshTokenNotFoundError(),
            trace_id=ctx.request_id,
            instance=_REFRESH_PATH,
        )

    credential = await auth_repo.find_by_user_id(new_record.user_id)
    if credential is None or not credential.is_active:
        return map_refresh_failure(
            AccountDisabledError("Account is deactivated."),
            trace_id=ctx.request_id,
            instance=_REFRESH_PATH,
        )

    settings = get_settings()
    now = datetime.now(UTC)
    access_token_expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    refresh_token_expires_at = new_record.expires_at

    claims = AccessTokenClaims(
        sub=str(new_record.user_id),
        jti=str(uuid.uuid4()),
        iat=now,
        exp=access_token_expires_at,
        nbf=now,
        iss=settings.jwt_issuer,
        aud=settings.jwt_audience,
        sid=str(new_record.session_id),
        email=str(credential.email),
        verified=credential.is_email_verified,
    )
    access_token = jwt_service.create_access_token(claims)

    session_response = SessionResponse(
        session_id=str(new_record.session_id),
        device_name=new_record.device_name,
        created_at=ctx.received_at,
    )

    user_response = UserResponse(
        user_id=str(credential.user_id),
        email=str(credential.email),
        is_email_verified=credential.is_email_verified,
    )

    response_data = LoginResponse(
        access_token=access_token,
        refresh_token=new_plain_token.as_client_token(),
        token_type="Bearer",
        access_token_expires_at=access_token_expires_at,
        refresh_token_expires_at=refresh_token_expires_at,
        session=session_response,
        user=user_response,
    )

    logger.info(
        "Token refresh succeeded",
        extra={
            "request_id": ctx.request_id,
            "user_id": str(new_record.user_id),
            "session_id": str(new_record.session_id),
        },
    )

    return JSONResponse(
        status_code=200,
        content=DataEnvelope(data=response_data).model_dump(mode="json"),
        headers={"X-Request-ID": ctx.request_id},
    )


@router.post(
    "/logout",
    status_code=204,
    summary="Log out of current session",
    operation_id="logoutUser",
    response_description="Session terminated successfully.",
)
async def logout(
    auth: RequireAuthentication,
    refresh_token_service: CurrentRefreshTokenService,
    session_repo: CurrentSessionRepository,
    ctx: CurrentRequestContext,
    body: LogoutRequest | None = None,
) -> Response:
    """
    Log out of the current session and revoke tokens.
    """
    if body and body.refresh_token:
        await refresh_token_service.revoke(presented_token=body.refresh_token)

    if auth.session_id:
        try:
            await refresh_token_service.revoke_all_for_session(
                session_id=SessionId(uuid.UUID(auth.session_id))
            )
            await session_repo.delete(session_id=SessionId(uuid.UUID(auth.session_id)))
        except Exception as e:
            logger.warning("Session cleanup on logout encountered error: %s", e)

    return Response(
        status_code=204,
        headers={"X-Request-ID": ctx.request_id},
    )

