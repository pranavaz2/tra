"""
AuthenticationSession aggregate root.

Represents an active login session. A session is bound to one user and
one refresh token at any point in time. Each /auth/refresh call rotates
the refresh token (previous is invalidated; new is issued).

Invariants enforced by this aggregate:
  - A session that is expired or revoked cannot rotate its refresh token.
  - revoke() is idempotent — calling it on an already-revoked session is safe.
  - is_active is the canonical check for session validity; it combines
    is_expired and is_revoked into a single predicate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.shared.domain.aggregate import AggregateRoot
from app.shared.domain.result import Failure, Result, Success
from app.modules.identity.authentication.domain.errors import (
    SessionExpiredError,
    SessionRevokedError,
)
from app.modules.identity.authentication.domain.events.authentication_events import (
    RefreshTokenRotated,
    RefreshTokenReuseDetected,
    SessionExpired,
    SessionRevokedDueToTokenReuse,
    UserLoggedIn,
    UserLoggedOut,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


@dataclass(kw_only=True, eq=False)
class AuthenticationSession(AggregateRoot[SessionId]):
    """
    Aggregate root for a user's authentication session.

    entity_id is the SessionId — unique per login event.

    ip_address and user_agent are optional audit fields; the domain stores
    them but never acts on them (that is a security-policy concern).
    """

    user_id: UserId
    refresh_token_id: RefreshTokenId
    expires_at: datetime
    last_active_at: datetime
    revoked_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        session_id: SessionId,
        user_id: UserId,
        refresh_token_id: RefreshTokenId,
        expires_at: datetime,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> "AuthenticationSession":
        """
        Create a new session and emit UserLoggedIn.

        expires_at must be timezone-aware (UTC).
        The caller is responsible for enforcing the concurrent session cap
        (MaxSessionsExceededError) before calling this factory.
        """
        now = datetime.now(UTC)
        session = cls(
            entity_id=session_id,
            user_id=user_id,
            refresh_token_id=refresh_token_id,
            expires_at=expires_at,
            last_active_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        session.push_event(
            UserLoggedIn(
                aggregate_id=str(session_id),
                user_id=str(user_id),
                session_id=str(session_id),
                ip_address=ip_address,
                user_agent=user_agent,
            )
        )
        return session

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                    #
    # ------------------------------------------------------------------ #

    @property
    def session_id(self) -> SessionId:
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_expired(self) -> bool:
        """True if the session TTL has elapsed."""
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        """True if the session was explicitly revoked (logout or security action)."""
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        """True if the session is neither expired nor revoked."""
        return not self.is_expired and not self.is_revoked

    # ------------------------------------------------------------------ #
    # Mutations                                                            #
    # ------------------------------------------------------------------ #

    def rotate_refresh_token(
        self,
        new_token_id: RefreshTokenId,
    ) -> Result[RefreshTokenId]:
        """
        Replace the current refresh token with new_token_id.

        Returns Success(previous_token_id) so the caller can immediately
        revoke the previous token in Redis.

        Returns Failure if the session is not active:
          - Failure(SessionExpiredError) if TTL elapsed.
          - Failure(SessionRevokedError) if explicitly revoked.

        Emits RefreshTokenRotated on success.
        """
        if self.is_expired:
            return Failure(SessionExpiredError())
        if self.is_revoked:
            return Failure(SessionRevokedError())

        previous_token_id = self.refresh_token_id
        self.refresh_token_id = new_token_id
        self.touch()
        self.push_event(
            RefreshTokenRotated(
                aggregate_id=str(self.session_id),
                user_id=str(self.user_id),
                session_id=str(self.session_id),
                previous_token_id=str(previous_token_id),
                new_token_id=str(new_token_id),
            )
        )
        return Success(previous_token_id)

    def revoke(self) -> None:
        """
        Revoke this session (voluntary logout or security action).

        Idempotent — safe to call multiple times. Emits UserLoggedOut only
        on the first call.
        """
        if self.is_revoked:
            return
        self.revoked_at = datetime.now(UTC)
        self.touch()
        self.push_event(
            UserLoggedOut(
                aggregate_id=str(self.session_id),
                user_id=str(self.user_id),
                session_id=str(self.session_id),
            )
        )

    def expire(self) -> None:
        """
        Mark this session as expired (called by the background expiry job).

        Emits SessionExpired. Does not set revoked_at — expiry and revocation
        are distinct lifecycle states.
        """
        self.push_event(
            SessionExpired(
                aggregate_id=str(self.session_id),
                user_id=str(self.user_id),
                session_id=str(self.session_id),
            )
        )

    def revoke_due_to_token_reuse(self, *, reused_token_hash_prefix: str = "") -> None:
        """
        Revoke this session as a security response to stolen-token reuse.

        Emits RefreshTokenReuseDetected (for security monitoring / alerting)
        followed by SessionRevokedDueToTokenReuse (for audit + session cleanup).

        Idempotent — safe to call on an already-revoked session.

        Callers must also:
          1. Revoke all RefreshTokenRecords for this session via RefreshTokenRepository.
          2. Blacklist any live JTIs for this session in the Redis revocation store.
        """
        if not self.is_revoked:
            self.push_event(
                RefreshTokenReuseDetected(
                    aggregate_id=str(self.session_id),
                    user_id=str(self.user_id),
                    session_id=str(self.session_id),
                    reused_token_hash_prefix=reused_token_hash_prefix,
                )
            )
        self.revoked_at = datetime.now(UTC)
        self.touch()
        self.push_event(
            SessionRevokedDueToTokenReuse(
                aggregate_id=str(self.session_id),
                user_id=str(self.user_id),
                session_id=str(self.session_id),
            )
        )

    def record_activity(self) -> None:
        """Update last_active_at to now (used by idle-timeout tracking)."""
        self.last_active_at = datetime.now(UTC)
        self.touch()
