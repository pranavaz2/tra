"""
RFC 7807 Problem Details error responses for the Authentication presentation layer.

All error responses follow the Authentication API Contract §3.5–3.7 and the
error catalogue in §6. No HTTP exceptions are raised — all failures produce a
JSONResponse directly so the caller can return it without try/except.

Error type URI convention:
  https://errors.travix.ai/auth/<kebab-case-error-name>

This matches the frozen API contract. The URIs will be dereferenceable to
documentation pages describing each error, its causes, and remediation steps.

Rate-limit extension point:
  The RateLimitInfo dataclass and _add_rate_limit_headers() function provide
  a typed extension point for future rate limiting middleware. When a real
  rate limiter is added, it should populate RateLimitInfo and pass it to the
  build_rate_limit_response() helper defined here.

Idempotency extension point:
  The Idempotency-Key header is documented here for future implementation.
  When implemented, the infrastructure layer stores the response body and
  status code keyed by (user_ip, idempotency_key) with a short TTL. Repeat
  requests with the same key return the stored response without re-executing
  the handler. Not yet persisted — see TASK-2.8.md §Idempotency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.identity.authentication.domain.errors import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticationFailedError,
    EmailAlreadyExistsError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidEmailError,
    PasswordHashingError,
    WeakPasswordError,
)
from app.shared.domain.errors import InfrastructureError, TravixError, UnauthorizedError

_AUTH_ERROR_BASE = "https://errors.travix.ai/auth"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"
_REGISTER_INSTANCE = "/api/v1/auth/register"
_LOGIN_INSTANCE = "/api/v1/auth/login"


# ──────────────────────────────────────────────────────────────────────────── #
# Rate limiting extension point                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


@dataclass(frozen=True)
class RateLimitInfo:
    """
    Rate limit metadata for HTTP response headers and 429 bodies.

    Extension point: populate this from a Redis-backed rate limiter and
    pass to _add_rate_limit_headers() or build_rate_limit_response().
    Registration endpoint target: 5 requests per hour per IP address.

    Recommended implementation: sliding window counter in Redis DB 3
    (redis_rate_limit_db). Key format: rate:register:<ip_address>.
    TTL: 3600 seconds. Value: current count in window.
    """

    limit: int
    remaining: int
    reset_unix: int
    retry_after_seconds: int | None = None


def add_rate_limit_headers(headers: dict[str, str], info: RateLimitInfo) -> None:
    """
    Mutate a header dict with standard rate-limit headers.

    Add to every response (not just 429s) per the API contract §3.7.
    Call this from the route handler or a middleware once rate limiting
    is implemented.

    Headers added:
      X-RateLimit-Limit     — max requests in the window
      X-RateLimit-Remaining — requests left in the current window
      X-RateLimit-Reset     — unix timestamp when the window resets
      Retry-After           — seconds until retry (429 responses only)
    """
    headers["X-RateLimit-Limit"] = str(info.limit)
    headers["X-RateLimit-Remaining"] = str(info.remaining)
    headers["X-RateLimit-Reset"] = str(info.reset_unix)
    if info.retry_after_seconds is not None:
        headers["Retry-After"] = str(info.retry_after_seconds)


def build_rate_limit_response(
    *,
    trace_id: str,
    retry_after_seconds: int,
    instance: str = _REGISTER_INSTANCE,
) -> JSONResponse:
    """
    Build a 429 Too Many Requests response conforming to §3.7.

    Called by the rate limiting middleware when the per-IP limit for
    registration (5 per hour) is exceeded. Not yet wired — extension point.
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(retry_after_seconds)},
        content={
            "type": f"{_AUTH_ERROR_BASE}/rate-limited",
            "title": "Too Many Requests",
            "status": status.HTTP_429_TOO_MANY_REQUESTS,
            "detail": (
                f"Too many registration attempts. "
                f"Try again in {retry_after_seconds} seconds."
            ),
            "instance": instance,
            "error_code": "AUTH_RATE_LIMITED",
            "trace_id": trace_id,
            "retry_after_seconds": retry_after_seconds,
        },
    )


# ──────────────────────────────────────────────────────────────────────────── #
# Problem Details builders                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


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
    """Build an RFC 7807 Problem Details body for auth-domain errors."""
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


def _validation_problem(
    *,
    trace_id: str,
    errors: list[dict[str, Any]],
    instance: str,
) -> dict[str, Any]:
    """Build an RFC 7807 + field-errors body for 422 validation failures."""
    return {
        "type": _VALIDATION_ERROR_TYPE,
        "title": "Validation Error",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": "One or more fields failed validation.",
        "instance": instance,
        "error_code": "VALIDATION_ERROR",
        "trace_id": trace_id,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────────────── #
# Result → HTTP mapping                                                          #
# ──────────────────────────────────────────────────────────────────────────── #


def map_registration_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str = _REGISTER_INSTANCE,
) -> JSONResponse:
    """
    Map a TravixError from RegistrationService.execute() to an RFC 7807 JSONResponse.

    Called by the route handler when result.is_ok is False. Matches every
    expected error type from the Application layer against the Authentication
    API Contract error catalogue (§6).

    Error hierarchy checked (most specific first):
      InvalidEmailError       → 422 VALIDATION_ERROR + AUTH_EMAIL_INVALID
      WeakPasswordError       → 422 VALIDATION_ERROR + AUTH_PASSWORD_TOO_WEAK (+ violations)
      EmailAlreadyExistsError → 409 AUTH_EMAIL_ALREADY_EXISTS
      PasswordHashingError    → 503 (infra failure; generic message to client)
      InfrastructureError     → 503 (infra failure; generic message to client)
      TravixError (other)     → 500 (unexpected; generic message to client)

    Security:
      503 and 500 responses never leak internal error messages or stack traces.
      Only the generic "service unavailable / unexpected error" string is sent.
      Full error details are captured by the structured logger at the call site.
    """
    if isinstance(error, InvalidEmailError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_validation_problem(
                trace_id=trace_id,
                instance=instance,
                errors=[
                    {
                        "field": "email",
                        "error_code": "AUTH_EMAIL_INVALID",
                        "message": "Enter a valid email address.",
                    }
                ],
            ),
        )

    if isinstance(error, WeakPasswordError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_validation_problem(
                trace_id=trace_id,
                instance=instance,
                errors=[
                    {
                        "field": "password",
                        "error_code": "AUTH_PASSWORD_TOO_WEAK",
                        "message": "Password does not meet strength requirements.",
                        "violations": error.violations,
                    }
                ],
            ),
        )

    if isinstance(error, EmailAlreadyExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_auth_problem(
                slug="email-already-exists",
                title="Email Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
                error_code="AUTH_EMAIL_ALREADY_EXISTS",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # PasswordHashingError is a subclass of InfrastructureError — check first
    if isinstance(error, (PasswordHashingError, InfrastructureError)):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_auth_problem(
                slug="service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Registration is temporarily unavailable. "
                    "Please try again shortly."
                ),
                error_code="AUTH_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # Unexpected TravixError subtype → 500
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_auth_problem(
            slug="internal-server-error",
            title="Internal Server Error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
            error_code="AUTH_INTERNAL_ERROR",
            trace_id=trace_id,
            instance=instance,
        ),
    )


def map_login_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str = _LOGIN_INSTANCE,
) -> JSONResponse:
    """
    Map a TravixError from LoginService.execute() to an RFC 7807 JSONResponse.

    Called by the route handler when result.is_ok is False. Matches every
    expected error type from the Application layer against the Authentication
    API Contract error catalogue (§6).

    Error hierarchy checked (most specific first):
      InvalidCredentialsError   → 401 AUTH_INVALID_CREDENTIALS
      AuthenticationFailedError → 401 AUTH_AUTHENTICATION_FAILED (risk block)
      UnauthorizedError (other) → 401 AUTH_UNAUTHORIZED
      AccountLockedError        → 423 AUTH_ACCOUNT_LOCKED (+ Retry-After header)
      AccountDisabledError      → 403 AUTH_ACCOUNT_DISABLED
      EmailNotVerifiedError     → 403 AUTH_EMAIL_NOT_VERIFIED
      PasswordHashingError      → 503 AUTH_SERVICE_UNAVAILABLE
      InfrastructureError       → 503 AUTH_SERVICE_UNAVAILABLE
      TravixError (other)       → 500 AUTH_INTERNAL_ERROR

    Security:
      401 responses use a generic message regardless of whether the email
      exists. This prevents user-enumeration via error message differences.
      503 and 500 responses never leak internal error messages or stack traces.
    """
    if isinstance(error, InvalidCredentialsError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_auth_problem(
                slug="invalid-credentials",
                title="Invalid Credentials",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
                error_code="AUTH_INVALID_CREDENTIALS",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, AuthenticationFailedError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_auth_problem(
                slug="authentication-failed",
                title="Authentication Failed",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication could not be completed. Please try again.",
                error_code="AUTH_AUTHENTICATION_FAILED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, UnauthorizedError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content=_auth_problem(
                slug="unauthorized",
                title="Unauthorized",
                http_status=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication is required.",
                error_code="AUTH_UNAUTHORIZED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # AccountLockedError is a ForbiddenError subclass but maps to 423 for login.
    # Check before AccountDisabledError to avoid the generic ForbiddenError branch.
    if isinstance(error, AccountLockedError):
        retry_after_seconds: int | None = None
        locked_until_iso: str | None = None
        response_headers: dict[str, str] = {}

        if error.locked_until is not None:
            from datetime import UTC, datetime as _dt

            remaining = max(0, int((error.locked_until - _dt.now(UTC)).total_seconds()))
            retry_after_seconds = remaining
            locked_until_iso = error.locked_until.isoformat()
            response_headers["Retry-After"] = str(remaining)

        return JSONResponse(
            status_code=status.HTTP_423_LOCKED,
            headers=response_headers,
            content=_auth_problem(
                slug="account-locked",
                title="Account Locked",
                http_status=status.HTTP_423_LOCKED,
                detail=str(error),
                error_code="AUTH_ACCOUNT_LOCKED",
                trace_id=trace_id,
                instance=instance,
                extra={
                    "locked_until": locked_until_iso,
                    "retry_after_seconds": retry_after_seconds,
                },
            ),
        )

    if isinstance(error, AccountDisabledError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_auth_problem(
                slug="account-disabled",
                title="Account Disabled",
                http_status=status.HTTP_403_FORBIDDEN,
                detail="This account has been disabled. Please contact support.",
                error_code="AUTH_ACCOUNT_DISABLED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, EmailNotVerifiedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_auth_problem(
                slug="email-not-verified",
                title="Email Not Verified",
                http_status=status.HTTP_403_FORBIDDEN,
                detail="Please verify your email address before logging in.",
                error_code="AUTH_EMAIL_NOT_VERIFIED",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # PasswordHashingError is a subclass of InfrastructureError — check first
    if isinstance(error, (PasswordHashingError, InfrastructureError)):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_auth_problem(
                slug="service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Login is temporarily unavailable. Please try again shortly.",
                error_code="AUTH_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # Unexpected TravixError subtype → 500
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_auth_problem(
            slug="internal-server-error",
            title="Internal Server Error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
            error_code="AUTH_INTERNAL_ERROR",
            trace_id=trace_id,
            instance=instance,
        ),
    )
