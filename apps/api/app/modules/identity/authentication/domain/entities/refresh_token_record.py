"""
RefreshTokenRecord domain entity.

Represents the complete lifecycle of a single refresh token from issuance
through rotation, expiry, or revocation.

Architecture notes:
  - Entity (NOT AggregateRoot): domain events are emitted by AuthenticationSession,
    the aggregate root that owns the session boundary.
  - identity: entity_id = RefreshTokenId (UUID primary key in the DB)
  - storage key: token_hash (SHA-256) — the column indexed for fast lookup
  - The plain token value is NEVER stored here or anywhere in the domain.

State machine (see ADR-005 for diagram):
  ACTIVE → ROTATED   token was used and replaced by a new one
  ACTIVE → EXPIRED   TTL elapsed (detected lazily on use)
  ACTIVE → REVOKED   explicit logout or security action
  ROTATED → REVOKED  revocation sweep after reuse detection
  EXPIRED → REVOKED  cleanup sweep

  ROTATED, EXPIRED, and REVOKED are terminal — no transitions out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum

from app.shared.domain.entity import Entity
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


class TokenState(str, Enum):
    """
    Lifecycle state of a RefreshTokenRecord.

    String-valued so it can be stored directly in the database without
    a separate mapping layer.
    """

    ACTIVE = "active"
    ROTATED = "rotated"   # Superseded; reuse of this token is a security event
    EXPIRED = "expired"   # TTL elapsed (lazy — detected at use time)
    REVOKED = "revoked"   # Explicitly revoked (logout, reuse sweep, password change)


_TERMINAL_STATES: frozenset[TokenState] = frozenset(
    {TokenState.ROTATED, TokenState.EXPIRED, TokenState.REVOKED}
)


@dataclass(kw_only=True, eq=False)
class RefreshTokenRecord(Entity[RefreshTokenId]):
    """
    Full lifecycle record for a single refresh token.

    The token_hash field is the primary lookup key: when a client presents
    a refresh token, the application computes SHA-256 of the presented value
    and queries by hash, never by the plain token itself.

    rotated_from and rotation_counter form an audit trail linking tokens
    within a session's rotation chain. rotation_counter starts at 0 for
    the first token issued to a session and increments on each rotation.

    Device fields (device_id, device_name, platform) are client-reported
    context — the server does NOT perform fingerprinting or behavioural
    analysis on them.
    """

    token_hash: RefreshTokenHash          # SHA-256 of the plaintext token
    session_id: SessionId
    user_id: UserId
    expires_at: datetime                  # UTC-aware expiry timestamp

    status: TokenState = TokenState.ACTIVE
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None
    rotated_from: RefreshTokenId | None = None   # Previous record's ID (audit chain)
    rotation_counter: int = 0                     # Depth in the session rotation chain
    token_version: int = 1                        # Bump to invalidate without revocation

    # Client-reported device context — no server-side fingerprinting
    device_id: str | None = None
    device_name: str | None = None
    platform: str | None = None

    # Token family for reuse-detection sweeps (TASK-2.12).
    # All tokens produced from a single login event share the same family_id.
    # When reuse is detected, the entire family is revoked rather than just
    # the single presented token, closing the window where a stolen earlier
    # token from the same session could still be rotated.
    # None on records created before this field was introduced (migration safe).
    token_family_id: str | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        record_id: RefreshTokenId,
        token_hash: RefreshTokenHash,
        session_id: SessionId,
        user_id: UserId,
        expires_at: datetime,
        rotated_from: RefreshTokenId | None = None,
        rotation_counter: int = 0,
        device_id: str | None = None,
        device_name: str | None = None,
        platform: str | None = None,
        token_family_id: str | None = None,
    ) -> "RefreshTokenRecord":
        """
        Create a new refresh token record in ACTIVE state.

        expires_at must be UTC-aware. rotated_from and rotation_counter
        are supplied when creating a replacement token during rotation.

        token_family_id groups all tokens from one login event. Pass the
        same value when rotating — the new token inherits the family.
        Omit (None) for records issued before TASK-2.12 was deployed.
        """
        return cls(
            entity_id=record_id,
            token_hash=token_hash,
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            status=TokenState.ACTIVE,
            rotated_from=rotated_from,
            rotation_counter=rotation_counter,
            device_id=device_id,
            device_name=device_name,
            platform=platform,
            token_family_id=token_family_id,
        )

    # ------------------------------------------------------------------ #
    # Derived state                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_expired(self) -> bool:
        """True if the token's wall-clock TTL has elapsed."""
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_usable(self) -> bool:
        """True iff the token is ACTIVE and has not yet expired."""
        return self.status == TokenState.ACTIVE and not self.is_expired

    @property
    def is_terminal(self) -> bool:
        """True if the token has reached a state with no outgoing transitions."""
        return self.status in _TERMINAL_STATES

    # ------------------------------------------------------------------ #
    # State mutations                                                      #
    # ------------------------------------------------------------------ #

    def mark_used(self) -> None:
        """Record that this token was presented (called before rotation)."""
        self.last_used_at = datetime.now(UTC)
        self.touch()

    def mark_rotated(self) -> None:
        """
        Transition to ROTATED (superseded by a new token).

        Idempotent if already in a terminal state. After this call,
        any future presentation of this token is a security event
        (see RefreshTokenReuseDetected).
        """
        if self.status != TokenState.ACTIVE:
            return
        self.status = TokenState.ROTATED
        self.touch()

    def mark_expired(self) -> None:
        """
        Transition to EXPIRED (called by background TTL sweep).

        Idempotent — no-op if already in a terminal state.
        """
        if self.status != TokenState.ACTIVE:
            return
        self.status = TokenState.EXPIRED
        self.touch()

    def revoke(self) -> None:
        """
        Transition to REVOKED (explicit logout or security revocation sweep).

        Idempotent — no-op if already REVOKED.
        ROTATED tokens can also be revoked (during full session sweep).
        """
        if self.status == TokenState.REVOKED:
            return
        self.status = TokenState.REVOKED
        self.revoked_at = datetime.now(UTC)
        self.touch()
