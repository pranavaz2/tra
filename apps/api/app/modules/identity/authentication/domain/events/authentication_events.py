"""
Authentication Domain Events.

All events are immutable facts — they record what happened, not what
should happen. Consumers must not mutate events.

Subclass constraint:
  DomainEvent uses @dataclass(frozen=True) WITHOUT kw_only=True, so its
  fields appear in the generated __init__ in positional order:
    aggregate_id: str (required, positional)
    event_id: UUID    (default factory)
    occurred_at: datetime (default factory)

  To avoid "non-default argument follows default argument" TypeError, every
  subclass uses @dataclass(frozen=True, kw_only=True). This makes all
  subclass-specific fields keyword-only, placed after the '*' separator in
  the generated __init__.

  Construction:
    event = UserRegistered(
        aggregate_id="<user-uuid>",   # positional-or-keyword from parent
        user_id="<user-uuid>",         # keyword-only from this class
        email="user@example.com",      # keyword-only from this class
    )

All id fields are stored as str (not UUID) so events remain serialisable
without importing UUID from the domain — events may be published to an
event bus and consumed by other contexts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserRegistered(DomainEvent):
    """
    Emitted when a new user account is created.

    aggregate_id: str(user_id) — the new user's identity.
    """

    user_id: str
    email: str


@dataclass(frozen=True, kw_only=True)
class UserLoggedIn(DomainEvent):
    """
    Emitted when a user successfully authenticates and a session is created.

    aggregate_id: str(session_id) — the newly created session.
    """

    user_id: str
    session_id: str
    ip_address: str | None = field(default=None)
    user_agent: str | None = field(default=None)


@dataclass(frozen=True, kw_only=True)
class UserLoggedOut(DomainEvent):
    """
    Emitted when a user explicitly revokes a session (voluntary logout).

    aggregate_id: str(session_id) — the revoked session.
    """

    user_id: str
    session_id: str


@dataclass(frozen=True, kw_only=True)
class SessionExpired(DomainEvent):
    """
    Emitted when a session is marked expired by the background expiry job.

    This is distinct from UserLoggedOut — expiry is passive (TTL elapsed),
    whereas logout is active (user intent).

    aggregate_id: str(session_id) — the expired session.
    """

    user_id: str
    session_id: str


@dataclass(frozen=True, kw_only=True)
class PasswordChanged(DomainEvent):
    """
    Emitted when a user's password hash is replaced.

    Consumers may use this to:
      - Invalidate all existing sessions (security policy).
      - Send a "your password was changed" notification email.

    aggregate_id: str(user_id) — the user whose password changed.
    """

    user_id: str


@dataclass(frozen=True, kw_only=True)
class RefreshTokenRotated(DomainEvent):
    """
    Emitted when a refresh token is rotated during a /auth/refresh call.

    The previous token must be revoked in Redis immediately after this event.
    If a consumer detects reuse of previous_token_id, it should raise
    RefreshTokenReuseError and invalidate the entire token family.

    aggregate_id: str(session_id) — the session that owns both tokens.
    """

    user_id: str
    session_id: str
    previous_token_id: str
    new_token_id: str


@dataclass(frozen=True, kw_only=True)
class RefreshTokenReuseDetected(DomainEvent):
    """
    Emitted when a ROTATED (superseded) refresh token is presented.

    This indicates a stolen token attack: either the attacker or the legitimate
    user is presenting a token that was already rotated. The entire session
    must be revoked immediately and the user should be notified.

    After this event, SessionRevokedDueToTokenReuse is emitted by the same
    session aggregate via revoke_due_to_token_reuse().

    aggregate_id: str(session_id) — the session containing the reused token.
    """

    user_id: str
    session_id: str
    reused_token_hash_prefix: str  # First 16 chars of the SHA-256 hash (for audit log)


@dataclass(frozen=True, kw_only=True)
class SessionRevokedDueToTokenReuse(DomainEvent):
    """
    Emitted when a session is revoked as a security response to token reuse.

    Distinct from UserLoggedOut (voluntary) and SessionExpired (passive).
    Consumers should:
      - Notify the user of suspicious activity.
      - Write to the security audit log.
      - Blacklist any active JTIs for this session in Redis.

    aggregate_id: str(session_id) — the session that was revoked.
    """

    user_id: str
    session_id: str


@dataclass(frozen=True, kw_only=True)
class EmailVerificationRequested(DomainEvent):
    """
    Emitted when a newly registered user must verify their email address.

    The registration service emits this event; it does NOT send the email
    directly. The notification service (subscriber) generates a one-time
    verification token, stores it (Redis + TTL), and dispatches the email.

    This separation keeps the registration flow synchronous and fast. Email
    delivery is an eventual side-effect, not a blocker.

    aggregate_id: str(user_id) — the user whose email needs verification.
    """

    user_id: str
    email: str


@dataclass(frozen=True, kw_only=True)
class UserEmailAutoVerified(DomainEvent):
    """
    Emitted when a user's email is auto-verified via configuration.

    This event is only raised when registration_auto_verify_email=True in
    application settings. It MUST NOT be emitted in production environments
    (enforced via the configuration interface — never hardcoded).

    Consumers may use this for audit logging in CI/local environments.

    aggregate_id: str(user_id) — the user whose email was auto-verified.
    """

    user_id: str
    email: str


@dataclass(frozen=True, kw_only=True)
class LoginAttemptFailed(DomainEvent):
    """
    Emitted on every failed login attempt regardless of reason.

    Consumers use this for:
      - Security monitoring, alerting, and SIEM integration.
      - Rate limiting audit trail (failed attempts per IP, per account).
      - Operational dashboards for brute-force detection.

    user_id is None when the email does not match any credential — this
    prevents the event payload from confirming whether an account exists.
    The failure_reason codes (see below) are intentionally coarse-grained
    to avoid leaking account state beyond what the HTTP response reveals.

    failure_reason values:
      "invalid_credentials" — wrong password or unknown email (no distinction)
      "account_disabled"    — account was permanently deactivated
      "account_locked"      — account is temporarily locked
      "email_not_verified"  — email verification is required but not complete
      "risk_blocked"        — risk assessment service blocked the login

    aggregate_id: str(user_id) if the email matched a credential, else "unknown".
    """

    failure_reason: str
    ip_address: str | None = field(default=None)
    user_id: str | None = field(default=None)
    user_agent: str | None = field(default=None)


@dataclass(frozen=True, kw_only=True)
class PasswordRehashed(DomainEvent):
    """
    Emitted when a credential's password hash is silently upgraded to a newer
    hashing algorithm or updated parameters (e.g., bcrypt → Argon2id, or
    Argon2id with increased memory cost).

    This is NOT a password change from the user's perspective — the plaintext
    password is identical; only the stored hash representation changed.

    Distinct from PasswordChanged to prevent:
      - Spurious "your password was changed" security notifications.
      - Incorrect password_changed_at updates (which affect PasswordExpiryPolicy
        and user-visible "last changed" timestamps).

    Raised by the LoginService as a service-level integration event, NOT by
    the AuthenticationCredential aggregate (transparent to the domain).

    aggregate_id: str(user_id) — the user whose hash was transparently upgraded.
    """

    user_id: str
