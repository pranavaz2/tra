"""
Authentication Domain Errors.

All expected failure states for the Authentication bounded context.
These map to HTTP status codes in app.core.exceptions; the mapping lives
there, not here — the domain has no knowledge of HTTP.

Error hierarchy:
  TravixError
  ├── ValidationError
  │   ├── InvalidEmailError          → 422 (bad email format)
  │   └── WeakPasswordError          → 422 (password fails policy)
  ├── DomainError
  │   ├── MaxSessionsExceededError   → 422 (business rule: concurrent sessions cap)
  │   ├── PasswordReuseError         → 422 (password was recently used)
  │   └── PasswordExpiredError       → 422 (password has exceeded its maximum age)
  ├── InfrastructureError
  │   ├── PasswordHashingError       → 503 (hashing library / HSM failure)
  │   └── PasswordGenerationError    → 503 (secure random generator failure)
  └── ApplicationError
      ├── UnauthorizedError
      │   ├── InvalidCredentialsError     → 401 (wrong email / password)
      │   ├── AuthenticationFailedError   → 401 (generic auth failure)
      │   ├── SessionExpiredError         → 401 (session TTL elapsed)
      │   ├── SessionRevokedError         → 401 (session was explicitly revoked)
      │   ├── RefreshTokenReuseError      → 401 (superseded token reused — stolen token)
      │   ├── RefreshTokenNotFoundError   → 401 (token hash has no matching record)
      │   ├── RefreshTokenExpiredError    → 401 (token TTL elapsed)
      │   └── RefreshTokenRevokedError    → 401 (token was explicitly revoked)
      ├── ForbiddenError
      │   ├── AccountDisabledError        → 403 (account permanently deactivated)
      │   ├── AccountLockedError          → 403 (account temporarily locked after failed attempts)
      │   └── EmailNotVerifiedError       → 403 (email address not yet verified)
      └── ConflictError
          └── EmailAlreadyExistsError     → 409 (email already registered)
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.shared.domain.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InfrastructureError,
    UnauthorizedError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Validation errors — user input failed a constraint
# ---------------------------------------------------------------------------


class InvalidEmailError(ValidationError):
    """The provided email address is not a valid format."""

    code = "invalid_email"

    def __init__(self, message: str = "The email address format is invalid.") -> None:
        super().__init__(message, field="email")


class WeakPasswordError(ValidationError):
    """The password does not satisfy the password policy."""

    code = "weak_password"

    def __init__(self, violations: list[str] | None = None) -> None:
        msg = "The password does not meet the required strength criteria."
        if violations:
            msg = f"{msg} Violations: {'; '.join(violations)}"
        super().__init__(msg, field="password")
        self.violations: list[str] = violations or []


# ---------------------------------------------------------------------------
# Unauthorized errors — caller lacks valid credentials or session
# ---------------------------------------------------------------------------


class InvalidCredentialsError(UnauthorizedError):
    """Email and password combination is incorrect."""

    code = "invalid_credentials"

    def __init__(self, message: str = "Email or password is incorrect.") -> None:
        super().__init__(message)


class AuthenticationFailedError(UnauthorizedError):
    """Authentication could not be completed."""

    code = "authentication_failed"

    def __init__(self, message: str = "Authentication failed.") -> None:
        super().__init__(message)


class SessionExpiredError(UnauthorizedError):
    """The session has passed its expiry time and is no longer valid."""

    code = "session_expired"

    def __init__(self, message: str = "The session has expired. Please log in again.") -> None:
        super().__init__(message)


class SessionRevokedError(UnauthorizedError):
    """The session has been explicitly revoked (logout or security action)."""

    code = "session_revoked"

    def __init__(self, message: str = "The session has been revoked. Please log in again.") -> None:
        super().__init__(message)


class RefreshTokenReuseError(UnauthorizedError):
    """
    A superseded refresh token was reused — indicates a stolen token.

    The entire token family should be invalidated on this event.
    See CLAUDE.md §11: refresh token rotation detects stolen tokens.
    """

    code = "refresh_token_reuse"

    def __init__(
        self,
        message: str = (
            "A revoked refresh token was used. "
            "All sessions for this account have been invalidated for security."
        ),
    ) -> None:
        super().__init__(message)


class RefreshTokenNotFoundError(UnauthorizedError):
    """
    The presented refresh token has no matching record.

    Either the token was never issued, its hash doesn't match any record,
    or the record was cleaned up after expiry. The caller cannot distinguish
    these cases — all produce the same generic error to prevent enumeration.
    """

    code = "refresh_token_invalid"

    def __init__(self, message: str = "The refresh token is invalid.") -> None:
        super().__init__(message)


class RefreshTokenExpiredError(UnauthorizedError):
    """The refresh token exists but its TTL has elapsed."""

    code = "refresh_token_expired"

    def __init__(
        self, message: str = "The refresh token has expired. Please log in again."
    ) -> None:
        super().__init__(message)


class RefreshTokenRevokedError(UnauthorizedError):
    """The refresh token was explicitly revoked (logout or security action)."""

    code = "refresh_token_revoked"

    def __init__(
        self, message: str = "The refresh token has been revoked. Please log in again."
    ) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Forbidden errors — authenticated but not permitted
# ---------------------------------------------------------------------------


class AccountDisabledError(ForbiddenError):
    """The user account has been deactivated and cannot authenticate."""

    code = "account_disabled"

    def __init__(self, message: str = "This account has been disabled.") -> None:
        super().__init__(message)


class AccountLockedError(ForbiddenError):
    """
    The account is temporarily locked due to too many consecutive failed login attempts.

    Unlike AccountDisabledError (permanent), this lock expires automatically once
    locked_until elapses. Clients should display a retry-after hint and not prompt
    the user to contact support.
    """

    code = "account_locked"

    def __init__(self, *, locked_until: datetime | None = None) -> None:
        if locked_until is not None:
            remaining_seconds = max(0, int((locked_until - datetime.now(UTC)).total_seconds()))
            remaining_minutes = max(1, (remaining_seconds + 59) // 60)
            msg = (
                f"This account is temporarily locked. "
                f"Please try again in {remaining_minutes} minute(s)."
            )
        else:
            msg = (
                "This account is temporarily locked due to too many failed login attempts. "
                "Please try again later."
            )
        super().__init__(msg)
        self.locked_until = locked_until


class EmailNotVerifiedError(ForbiddenError):
    """
    The user's email address has not been verified.

    Raised when AuthenticationPolicy.require_email_verification is True and the
    credential's is_email_verified flag is False. The user must complete email
    verification before logging in.
    """

    code = "email_not_verified"

    def __init__(
        self,
        message: str = "Please verify your email address before logging in.",
    ) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Conflict errors — request conflicts with current resource state
# ---------------------------------------------------------------------------


class EmailAlreadyExistsError(ConflictError):
    """An account with the given email address already exists."""

    code = "email_already_exists"

    def __init__(self, email: str | None = None) -> None:
        msg = "An account with this email address already exists."
        super().__init__(msg)
        self.email = email


# ---------------------------------------------------------------------------
# Domain errors — business invariant violations
# ---------------------------------------------------------------------------


class MaxSessionsExceededError(DomainError):
    """Creating a new session would exceed the concurrent session limit."""

    code = "max_sessions_exceeded"

    def __init__(self, max_sessions: int | None = None) -> None:
        limit_note = f" (limit: {max_sessions})" if max_sessions is not None else ""
        super().__init__(
            f"Maximum number of concurrent sessions reached{limit_note}. "
            "Please log out of another device before logging in again."
        )
        self.max_sessions = max_sessions


class PasswordReuseError(DomainError):
    """
    The new password was recently used and violates the password history policy.

    The domain raises this when the application layer detects that a candidate
    password matches one of the stored previous hashes (via PasswordHasher.verify).
    """

    code = "password_reuse"

    def __init__(self, history_count: int | None = None) -> None:
        count_note = (
            f" (your last {history_count} passwords cannot be reused)"
            if history_count is not None
            else ""
        )
        super().__init__(
            f"This password has been used recently{count_note}. "
            "Please choose a different password."
        )
        self.history_count = history_count


class PasswordExpiredError(DomainError):
    """
    The credential's password has exceeded its maximum allowed age.

    Raised by the application layer when PasswordExpiryPolicy.max_password_age
    has elapsed since the credential's password_changed_at timestamp.
    The user must change their password before proceeding.
    """

    code = "password_expired"

    def __init__(self, message: str = "Your password has expired. Please set a new password.") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Infrastructure errors — hashing subsystem failures
# ---------------------------------------------------------------------------


class PasswordHashingError(InfrastructureError):
    """
    The password hashing or verification operation failed.

    This is NOT raised for incorrect passwords (that returns False from
    PasswordHasher.verify). It is raised for INFRASTRUCTURE failures:
      - The hashing library is unavailable.
      - The stored hash is structurally corrupt (not a recognised format).
      - An external HSM / KMS call failed.

    Callers should treat this as a 503 Service Unavailable.
    """

    code = "password_hashing_error"

    def __init__(
        self,
        message: str = "Password hashing operation failed.",
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)


class PasswordGenerationError(InfrastructureError):
    """
    The secure random password generator could not produce a valid password.

    Raised when the generator exhausts its retry budget trying to produce
    a password that satisfies PasswordStrengthPolicy — this should be
    extremely rare and indicates a misconfigured policy or RNG failure.
    """

    code = "password_generation_error"

    def __init__(
        self,
        message: str = "Failed to generate a password satisfying the current policy.",
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message, cause=cause)
