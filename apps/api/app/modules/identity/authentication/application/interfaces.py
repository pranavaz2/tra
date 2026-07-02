"""
Authentication Application Service Contracts.

These Protocols define use-case-level interfaces for password management
operations. FastAPI route handlers depend on these interfaces — never on
concrete implementations. This enables:
  - Testing route handlers with test doubles that satisfy the Protocol.
  - Swapping implementations (e.g., adding feature flags, A/B flows)
    without changing the API layer.

Placement rationale:
  These are APPLICATION-layer contracts (not domain-layer). They orchestrate
  domain objects and infrastructure adapters. They are NOT domain services —
  domain services operate only on domain types with no I/O.

All methods are async — application use cases always perform I/O
(database reads/writes, email sending, cache invalidation).

Input types are domain value objects or primitives. Application services
receive validated, typed inputs — raw strings from the HTTP layer must be
converted before being passed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from app.shared.domain.result import Result
from app.modules.identity.authentication.application.commands import (
    LoginUserCommand,
    RegisterUserCommand,
)
from app.modules.identity.authentication.application.dtos import LoginResult, RegistrationResult
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


# ---------------------------------------------------------------------------
# Risk Assessment types (used by RiskAssessmentService and LoginService)
# ---------------------------------------------------------------------------


class RiskAction(Enum):
    """
    Decision returned by RiskAssessmentService.assess().

    ALLOW:     Proceed with login normally.
    CHALLENGE: Require step-up authentication (MFA, OTP) before issuing tokens.
               Currently treated as ALLOW — step-up auth is deferred to TASK-2.x.
    BLOCK:     Deny the login immediately; return AuthenticationFailedError.
    """

    ALLOW = "allow"
    CHALLENGE = "challenge"
    BLOCK = "block"


@dataclass(frozen=True)
class RiskDecision:
    """
    Output of a risk assessment evaluation for a login attempt.

    Attributes:
        action:      What the login service should do (ALLOW / CHALLENGE / BLOCK).
        reason:      Human-readable rationale for the logging and audit trail.
        risk_score:  Normalised risk score in [0.0, 1.0]. 0.0 = no risk detected.
    """

    action: RiskAction
    reason: str | None = None
    risk_score: float = 0.0


@dataclass(frozen=True)
class RiskSignals:
    """
    Pre-computed risk signals passed to RiskAssessmentService.assess().

    These signals are detected by the calling layer (e.g., through IP
    reputation databases, device fingerprinting, or geolocation checks)
    before the risk service is called. The risk service combines them
    with its own internal evaluation to produce a RiskDecision.

    All signals are optional and default to their lowest-risk state so that
    callers only populate the signals they have data for. Unknown signal
    values are treated as no signal by the risk engine.

    Signals:
        is_new_device:           True if device_id has never been seen for
                                 this user before. Triggers additional
                                 verification in some risk engines.
        is_impossible_travel:    True if the login IP is geographically
                                 inconsistent with the user's recent activity
                                 (e.g., Paris login 5 minutes after Tokyo login).
        is_anonymous_proxy:      True if the IP is associated with a known
                                 anonymous proxy service (Tor, open proxy, etc.).
        is_tor_exit_node:        True if the IP is a confirmed Tor exit node.
                                 Distinct from anonymous_proxy — some operators
                                 treat Tor differently from commercial VPNs.
        velocity_anomaly_score:  Normalised [0.0, 1.0] score representing login
                                 rate anomalies for this user or IP.
                                 0.0 = no anomaly; 1.0 = severe rate spike.
        previous_ip_address:     The IP address from the user's most recent
                                 prior login, for impossible-travel calculation.
        known_device_ids:        Sorted list of device IDs the user has
                                 previously authenticated from, for new-device
                                 signal computation by the risk engine.
    """

    is_new_device: bool = False
    is_impossible_travel: bool = False
    is_anonymous_proxy: bool = False
    is_tor_exit_node: bool = False
    velocity_anomaly_score: float = 0.0
    previous_ip_address: str | None = None
    known_device_ids: tuple[str, ...] = ()


@runtime_checkable
class ChangePasswordService(Protocol):
    """
    Use-case interface for an authenticated user changing their own password.

    Flow:
      1. Load the credential for user_id.
      2. Verify current_password against the stored hash.
      3. Check new_password against PasswordStrengthPolicy.
      4. Check new_password against PasswordHistoryPolicy (reuse).
      5. Hash new_password.
      6. Call credential.change_password(new_hash).
      7. Revoke all OTHER active sessions (security: force re-login on all devices).
      8. Persist and commit.
      9. Emit PasswordChanged domain event to notification service.
    """

    async def execute(
        self,
        *,
        user_id: UserId,
        current_password: str,
        new_password: str,
    ) -> Result[None]:
        """
        Change the password for the authenticated user.

        Args:
            user_id:          The user requesting the change (from JWT claim).
            current_password: The user's current password for re-authentication.
            new_password:     The desired new password in plaintext.

        Returns:
            Success(None)                 on success.
            Failure(InvalidCredentialsError)  if current_password is wrong.
            Failure(AccountDisabledError)     if the account is inactive.
            Failure(WeakPasswordError)        if new_password fails policy.
            Failure(PasswordReuseError)       if new_password was recently used.
        """
        ...


@runtime_checkable
class ResetPasswordService(Protocol):
    """
    Use-case interface for resetting a forgotten password.

    Two-step flow:
      Step 1 — initiate_reset:   User provides their email. A reset token is
                                  generated, stored, and emailed. Returns Success
                                  even if the email is not found (prevents user
                                  enumeration).

      Step 2 — complete_reset:   User provides the token and new password. The
                                  token is validated, the password is changed, and
                                  all sessions are revoked.

    Token details are infrastructure concerns — the domain only knows the token
    as a str. Token format, storage (Redis, DB), expiry, and single-use
    enforcement are handled in the infrastructure layer.
    """

    async def initiate_reset(self, *, email: Email) -> Result[None]:
        """
        Begin the password reset flow.

        Always returns Success(None) regardless of whether the email exists,
        to prevent account enumeration.

        Side effects:
          - Generates a one-time reset token.
          - Stores the token with a short TTL (infrastructure — e.g., Redis).
          - Sends a password-reset email via EmailProvider.

        Returns:
            Success(None) always (even for unknown emails).
        """
        ...

    async def complete_reset(
        self,
        *,
        reset_token: str,
        new_password: str,
    ) -> Result[None]:
        """
        Complete the password reset using a token from the reset email.

        Args:
            reset_token:  The one-time token from the reset email.
            new_password: The new password in plaintext.

        Returns:
            Success(None)                 on success.
            Failure(AuthenticationFailedError)  if token is invalid or expired.
            Failure(WeakPasswordError)          if new_password fails policy.
            Failure(AccountDisabledError)       if the account is inactive.
        """
        ...


@runtime_checkable
class RefreshTokenService(Protocol):
    """
    Use-case interface for refresh token lifecycle management.

    Orchestrates token generation, hashing, storage, rotation, and revocation.
    All token crypto is delegated to domain service protocols (RefreshTokenGenerator,
    RefreshTokenHasher). All storage is delegated to RefreshTokenRepository.

    This interface is the only entry point for refresh token operations in the
    application layer — route handlers must NOT interact with the repository directly.
    """

    async def issue(
        self,
        *,
        session_id: SessionId,
        user_id: UserId,
        expires_at: datetime,
        device_id: str | None = None,
        device_name: str | None = None,
        platform: str | None = None,
    ) -> Result[tuple[PlainRefreshToken, RefreshTokenId]]:
        """
        Issue a brand-new refresh token for a newly created session.

        Generates a 256-bit token, hashes it, persists the record, and
        returns (plain_token, record_id). The caller (login / registration
        service) must store record_id as the session's refresh_token_id.

        Args:
            session_id:   The session this token is issued for.
            user_id:      The user who owns the session.
            expires_at:   UTC expiry timestamp for the token.
            device_id:    Client-reported device identifier (optional).
            device_name:  Human-readable device label (optional).
            platform:     Client platform string — "ios", "android", etc. (optional).

        Returns:
            Success((plain_token, record_id)) on success.
            Failure(InfrastructureError) if storage fails.
        """
        ...

    async def rotate(
        self,
        *,
        presented_token: str,
        device_id: str | None = None,
        device_name: str | None = None,
        platform: str | None = None,
    ) -> Result[tuple[PlainRefreshToken, RefreshTokenId]]:
        """
        Rotate: validate the presented token, issue a new one, revoke the old one.

        The rotation is ATOMIC — the old record is marked ROTATED and the new
        record is inserted as ACTIVE within a single store operation.

        If the presented token's record is already ROTATED (stolen-token reuse):
          - The entire session is revoked immediately.
          - RefreshTokenReuseDetected and SessionRevokedDueToTokenReuse events are pushed.
          - Failure(RefreshTokenReuseError) is returned.

        Args:
            presented_token: The raw token string from the HTTP request body.
            device_id, device_name, platform: Client context (may update the record).

        Returns:
            Success((new_plain_token, new_record_id)) on success.
            Failure(RefreshTokenNotFoundError) if token hash has no record.
            Failure(RefreshTokenExpiredError)  if token TTL elapsed.
            Failure(RefreshTokenRevokedError)  if token was explicitly revoked.
            Failure(RefreshTokenReuseError)    if token was already rotated (stolen token).
            Failure(SessionExpiredError)       if the owning session expired.
            Failure(SessionRevokedError)       if the owning session is revoked.
        """
        ...

    async def revoke(
        self,
        *,
        presented_token: str,
    ) -> Result[None]:
        """
        Revoke a specific refresh token (single-device logout).

        Marks the record as REVOKED. Does NOT revoke the owning session or
        other tokens for the same session.

        Returns:
            Success(None)                      on success (idempotent).
            Failure(RefreshTokenNotFoundError) if token is unknown.
        """
        ...

    async def revoke_all_for_session(
        self,
        *,
        session_id: SessionId,
    ) -> Result[int]:
        """
        Revoke all active refresh tokens for a session.

        Used on:
          - Explicit logout (single session revoked via revoke_session).
          - Reuse detection (all tokens swept after revoke_due_to_token_reuse).

        Returns:
            Success(n) where n is the number of records revoked.
        """
        ...

    async def revoke_all_for_user(
        self,
        *,
        user_id: UserId,
    ) -> Result[int]:
        """
        Revoke all refresh tokens for all sessions of a user.

        Used on password change and account compromise response (logout-all).

        Returns:
            Success(n) where n is the total number of records revoked.
        """
        ...


@runtime_checkable
class SessionRevocationService(Protocol):
    """
    Use-case interface for revoking authentication sessions.

    Separates session revocation (SessionRepository) from token revocation
    (RefreshTokenRepository) so each can be called independently or together.
    """

    async def revoke_session(
        self,
        *,
        session_id: SessionId,
        reason: str = "logout",
    ) -> Result[None]:
        """
        Revoke a single authentication session.

        Loads the session, calls session.revoke(), persists, and pops events.

        Returns:
            Success(None) on success (idempotent if already revoked).
            Failure(NotFoundError) if session does not exist.
        """
        ...

    async def revoke_all_sessions_for_user(
        self,
        *,
        user_id: UserId,
    ) -> Result[int]:
        """
        Revoke all sessions for a user (logout-all / compromise response).

        Returns:
            Success(n) where n is the number of sessions revoked.
        """
        ...


@runtime_checkable
class TokenRevocationService(Protocol):
    """
    Application interface for the JWT JTI blacklist (Redis-backed).

    Manages the Redis revocation store that the auth middleware queries
    on every request. Implementations use redis_token_revocation_db (DB 2)
    with AOF persistence (loss of this DB is a security vulnerability).
    """

    async def revoke_jti(
        self,
        *,
        jti: str,
        expires_at: datetime,
    ) -> None:
        """
        Add a JTI to the revocation blacklist.

        The entry TTL is set to the access token's remaining lifetime so
        Redis self-cleans expired entries. Calling this after the JTI's
        natural expiry is a no-op.

        Args:
            jti:        The JWT ID from the access token's 'jti' claim.
            expires_at: The token's 'exp' claim (UTC). Determines Redis TTL.
        """
        ...

    async def is_revoked(self, *, jti: str) -> bool:
        """
        Return True if the given JTI is on the blacklist.

        Called by auth middleware on every protected request AFTER signature
        validation. A missing Redis key means the token is NOT revoked.
        """
        ...


@runtime_checkable
class RegistrationService(Protocol):
    """
    Use-case interface for new user registration.

    Orchestrates: email validation → uniqueness check → password hashing →
    credential creation → verification workflow → optional session →
    atomic commit → domain event publication.

    FastAPI route handlers depend only on this Protocol, never on the
    concrete RegistrationService class. This allows the concrete service
    to be swapped or decorated (e.g., with rate-limiting, audit hooks)
    without touching the API layer.
    """

    async def execute(self, command: RegisterUserCommand) -> RegistrationResult:
        """
        Register a new user and return a typed Result.

        Args:
            command: RegisterUserCommand carrying the raw email and password.

        Returns:
            Success(RegistrationSummary)     — registration succeeded.
            Failure(InvalidEmailError)       — email format is invalid.
            Failure(EmailAlreadyExistsError) — email already registered.
            Failure(WeakPasswordError)       — password fails strength policy.
            Failure(PasswordHashingError)    — hashing subsystem failure.
            Failure(InfrastructureError)     — database or token-service failure.
        """
        ...


@runtime_checkable
class ValidatePasswordService(Protocol):
    """
    Use-case interface for checking a password against all active policies
    BEFORE the user attempts to set it.

    Intended for real-time client feedback (e.g., a strength meter that
    updates as the user types). Call this endpoint before calling register
    or change-password to surface policy violations early.

    This operation has NO side effects — it is a pure read.
    """

    async def get_violations(self, *, password: str) -> list[str]:
        """
        Return a list of human-readable policy violation descriptions.

        An empty list means the password would be accepted. Non-empty means
        it would be rejected; each string explains one violation.

        Checks applied (in order):
          1. PasswordStrengthPolicy (length, character diversity)
          2. PasswordComplexityPolicy (uppercase, digits, special chars)
          3. Common password / dictionary word check (if configured)

        Note: History checks (PasswordHistoryPolicy) are NOT applied here —
        history requires a user identity, which is not available at validation
        time (e.g., during registration).

        Args:
            password: The plaintext password to evaluate.

        Returns:
            List of violation strings. Empty = password is acceptable.
        """
        ...


@runtime_checkable
class RiskAssessmentService(Protocol):
    """
    Use-case interface for evaluating the risk of a login attempt.

    Provides an integration point for adaptive authentication. When a concrete
    implementation is wired into the DI container, LoginService calls it between
    account-state checks and password verification. When no implementation is
    configured (None), the login service proceeds as ALLOW.

    Signals a concrete implementation may evaluate (non-exhaustive):
      - Trusted device recognition (device_id + device fingerprint history)
      - Unusual geolocation compared to prior sessions
      - Impossible travel (login from two geographically distant locations
        in a time window too short for physical travel)
      - Suspicious login frequency (many attempts per time window)
      - Anonymous proxy / VPN / Tor exit node detection

    The interface is intentionally opaque to LoginService — it returns only
    a RiskDecision. The implementation details (IP reputation API, ML model,
    rule engine) are invisible to the application layer.

    Adding a concrete implementation requires:
      1. A class implementing this Protocol.
      2. Wiring it in infrastructure/dependencies.py.
    No changes to LoginService are required.
    """

    async def assess(
        self,
        *,
        user_id: str | None,
        email: str,
        ip_address: str | None,
        user_agent: str | None,
        device_id: str | None,
        signals: RiskSignals | None = None,
    ) -> RiskDecision:
        """
        Evaluate the risk of a login attempt and return an action decision.

        Called after account-state checks (disabled, locked, unverified) and
        before password verification. Password is NOT passed — the risk service
        must not access credentials.

        Args:
            user_id:    The user's UUID string if the email was found, else None.
                        None indicates the email is unknown; the risk service
                        should still evaluate IP reputation signals.
            email:      The normalised email from the login request.
            ip_address: Client IP address (may be None if not available).
            user_agent: HTTP User-Agent header value (may be None).
            device_id:  Client-reported device identifier (may be None).
            signals:    Pre-computed risk signals (impossible travel, new device,
                        anonymous proxy, Tor, velocity anomalies). When None,
                        the risk service computes all signals internally.
                        When provided, the service uses them as hints and may
                        still supplement with its own evaluation.

        Returns:
            RiskDecision with action=ALLOW, CHALLENGE, or BLOCK.
            Must not raise — any internal failure should return ALLOW
            with a reason string describing the failure, so that risk
            service unavailability does not block all logins.
        """
        ...


@runtime_checkable
class LoginService(Protocol):
    """
    Use-case interface for password-based user authentication.

    Orchestrates: email validation → credential lookup → account state checks
    → optional risk assessment → password verification → session creation →
    token issuance → atomic commit → domain event publication.

    FastAPI route handlers depend only on this Protocol, never on the concrete
    LoginService class. This decoupling allows the service to be wrapped with
    rate-limiting decorators, A/B logic, or audit hooks without changing the
    API layer.
    """

    async def execute(self, command: LoginUserCommand) -> LoginResult:
        """
        Authenticate a user and return a typed Result.

        Args:
            command: LoginUserCommand carrying the raw email and password.

        Returns:
            Success(AuthenticatedSessionSummary) — login succeeded.
            Failure(InvalidCredentialsError)     — wrong password or unknown email.
            Failure(AccountDisabledError)        — account permanently deactivated.
            Failure(AccountLockedError)          — account temporarily locked.
            Failure(EmailNotVerifiedError)       — email verification required.
            Failure(AuthenticationFailedError)   — blocked by risk assessment.
            Failure(PasswordHashingError)        — hashing subsystem failure.
            Failure(InfrastructureError)         — database or token-service failure.
        """
        ...
