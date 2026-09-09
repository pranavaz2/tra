"""
RefreshTokenApplicationService — orchestrates the refresh token lifecycle.

This is an APPLICATION SERVICE: it coordinates domain objects and infrastructure
adapters without containing business logic. Business rules live in the domain
entities (RefreshTokenRecord.is_usable, AuthenticationSession.rotate_refresh_token).

Responsibilities:
  - issue():  Generate → hash → persist → return to caller.
  - rotate(): Validate → atomic rotate → update session → return new token.
  - revoke(): Hash → find → mark REVOKED → persist.
  - revoke_all_for_session(): Sweep all records for a session.
  - revoke_all_for_user():    Sweep all records across all sessions.

Atomicity:
  rotate() delegates atomicity to RefreshTokenRepository.rotate(). For the
  InMemoryRefreshTokenStore, this is an asyncio.Lock. For PostgreSQL, this
  must be a SELECT FOR UPDATE within a SERIALIZABLE transaction.

  Session update (AuthenticationSession.refresh_token_id = new_record_id) is
  performed AFTER the atomic token swap. In a production PostgreSQL implementation
  both operations must be in the same database transaction. The in-memory
  implementation accepts the small window between the two operations.

Dependencies are injected via the constructor. The class depends only on
Protocol interfaces — no concrete infrastructure types are imported.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.shared.domain.errors import NotFoundError
from app.shared.domain.result import Failure, Result, Success
from app.modules.identity.authentication.domain.entities.refresh_token_record import (
    RefreshTokenRecord,
    TokenState,
)
from app.modules.identity.authentication.domain.errors import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReuseError,
    RefreshTokenRevokedError,
    SessionExpiredError,
    SessionRevokedError,
)
from app.modules.identity.authentication.domain.repositories.interfaces import (
    RefreshTokenRepository,
    SessionRepository,
)
from app.modules.identity.authentication.domain.services.refresh_token_protocols import (
    RefreshTokenGenerator,
    RefreshTokenHasher,
)
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class RefreshTokenApplicationService:
    """
    Orchestrates refresh token lifecycle operations.

    Implements RefreshTokenService Protocol (application/interfaces.py).
    All dependencies are injected via constructor — no globals, no os.environ.
    """

    def __init__(
        self,
        *,
        token_store: RefreshTokenRepository,
        session_repository: SessionRepository,
        generator: RefreshTokenGenerator,
        hasher: RefreshTokenHasher,
        token_lifetime_days: int,
    ) -> None:
        self._store = token_store
        self._sessions = session_repository
        self._generator = generator
        self._hasher = hasher
        self._lifetime = timedelta(days=token_lifetime_days)

    # ------------------------------------------------------------------ #
    # issue                                                                #
    # ------------------------------------------------------------------ #

    async def issue(
        self,
        *,
        session_id: SessionId,
        user_id: UserId,
        expires_at: datetime,
        record_id: RefreshTokenId | None = None,
        device_id: str | None = None,
        device_name: str | None = None,
        platform: str | None = None,
    ) -> Result[tuple[PlainRefreshToken, RefreshTokenId]]:
        """
        Issue a new refresh token for a freshly created session.

        Returns (plain_token, record_id).
        """
        plain = self._generator.generate()
        token_hash = self._hasher.hash(plain)
        effective_record_id = record_id or RefreshTokenId.generate()

        record = RefreshTokenRecord.create(
            record_id=effective_record_id,
            token_hash=token_hash,
            session_id=session_id,
            user_id=user_id,
            expires_at=expires_at,
            device_id=device_id,
            device_name=device_name,
            platform=platform,
        )
        await self._store.save(record)

        logger.debug(
            "Refresh token issued",
            extra={
                "session_id": str(session_id),
                "record_id": str(effective_record_id),
                "hash_prefix": token_hash.value[:16],
            },
        )
        return Success((plain, effective_record_id))

    # ------------------------------------------------------------------ #
    # rotate                                                               #
    # ------------------------------------------------------------------ #

    async def rotate(
        self,
        *,
        presented_token: str,
        device_id: str | None = None,
        device_name: str | None = None,
        platform: str | None = None,
    ) -> Result[tuple[PlainRefreshToken, RefreshTokenId]]:
        """
        Validate the presented token, issue a replacement, revoke the old one.

        Rotation flow:
          1. Hash the presented token.
          2. Look up the record (pre-lock check for fast failure).
          3. Validate record state.
          4. Generate new token + record.
          5. Atomic rotate (lock-protected re-validate + swap).
          6. Update AuthenticationSession.refresh_token_id.
          7. Return new token.

        Step 5 re-validates under the lock — any state change between steps
        2 and 5 (concurrent rotation) is caught and handled correctly.
        """
        plain = PlainRefreshToken.from_client(presented_token)
        token_hash = self._hasher.hash(plain)

        # Pre-lock validation (fast path for obviously invalid tokens)
        old_record = await self._store.find_by_hash(token_hash)

        if old_record is None:
            return Failure(RefreshTokenNotFoundError())

        # Stolen-token detection: ROTATED → revoke entire session immediately.
        if old_record.status == TokenState.ROTATED:
            await self._handle_token_reuse(old_record, token_hash.value[:16])
            return Failure(RefreshTokenReuseError())

        if old_record.status == TokenState.REVOKED:
            return Failure(RefreshTokenRevokedError())

        if old_record.is_expired:
            return Failure(RefreshTokenExpiredError())

        # Validate the owning session.
        session = await self._sessions.find_by_id(old_record.session_id)
        if session is None:
            return Failure(RefreshTokenNotFoundError("Session not found for this token."))
        if session.is_expired:
            return Failure(SessionExpiredError())
        if session.is_revoked:
            return Failure(SessionRevokedError())

        # Build replacement record.
        new_plain = self._generator.generate()
        new_hash = self._hasher.hash(new_plain)
        new_record_id = RefreshTokenId.generate()
        now = datetime.now(UTC)

        new_record = RefreshTokenRecord.create(
            record_id=new_record_id,
            token_hash=new_hash,
            session_id=old_record.session_id,
            user_id=old_record.user_id,
            expires_at=now + self._lifetime,
            rotated_from=old_record.entity_id,
            rotation_counter=old_record.rotation_counter + 1,
            device_id=device_id or old_record.device_id,
            device_name=device_name or old_record.device_name,
            platform=platform or old_record.platform,
        )

        # Atomic swap: raises on concurrent rotation or reuse.
        try:
            await self._store.rotate(old_hash=token_hash, new_record=new_record)
        except RefreshTokenReuseError:
            # Lost the race — another concurrent request rotated this token first.
            await self._handle_token_reuse(old_record, token_hash.value[:16])
            return Failure(RefreshTokenReuseError())
        except (RefreshTokenNotFoundError, RefreshTokenRevokedError, RefreshTokenExpiredError) as exc:
            return Failure(exc)

        # Update the session's current token pointer.
        # Production note: this and the rotate() above must be in the same DB transaction.
        rotation_result = session.rotate_refresh_token(new_record_id)
        if rotation_result.is_ok:
            await self._sessions.save(session)
        else:
            # Session state changed between our check and now (concurrent logout, etc.)
            # The new token exists but the session is stale. Revoke the new token.
            new_record.revoke()
            await self._store.save(new_record)
            return Failure(rotation_result.error)

        logger.debug(
            "Refresh token rotated",
            extra={
                "session_id": str(old_record.session_id),
                "new_record_id": str(new_record_id),
                "rotation_counter": new_record.rotation_counter,
            },
        )
        return Success((new_plain, new_record_id))

    # ------------------------------------------------------------------ #
    # revoke (single token)                                                #
    # ------------------------------------------------------------------ #

    async def revoke(self, *, presented_token: str) -> Result[None]:
        """Revoke a specific refresh token (single-device logout)."""
        plain = PlainRefreshToken.from_client(presented_token)
        token_hash = self._hasher.hash(plain)

        record = await self._store.find_by_hash(token_hash)
        if record is None:
            return Failure(RefreshTokenNotFoundError())

        record.revoke()
        await self._store.save(record)
        return Success(None)

    # ------------------------------------------------------------------ #
    # revoke_all_for_session                                               #
    # ------------------------------------------------------------------ #

    async def revoke_all_for_session(self, *, session_id: SessionId) -> Result[int]:
        """Revoke all active refresh tokens for a session."""
        count = await self._store.revoke_all_for_session(session_id)
        logger.debug(
            "All refresh tokens revoked for session",
            extra={"session_id": str(session_id), "count": count},
        )
        return Success(count)

    # ------------------------------------------------------------------ #
    # revoke_all_for_user                                                  #
    # ------------------------------------------------------------------ #

    async def revoke_all_for_user(self, *, user_id: UserId) -> Result[int]:
        """Revoke all refresh tokens for all sessions of a user."""
        count = await self._store.revoke_all_for_user(user_id)
        logger.debug(
            "All refresh tokens revoked for user",
            extra={"user_id": str(user_id), "count": count},
        )
        return Success(count)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _handle_token_reuse(
        self,
        old_record: RefreshTokenRecord,
        hash_prefix: str,
    ) -> None:
        """
        Respond to stolen-token reuse detection.

        Revokes all tokens for the session and marks the session as revoked
        due to token reuse (which emits RefreshTokenReuseDetected and
        SessionRevokedDueToTokenReuse domain events via the aggregate).

        This is a best-effort security response — if the session or sweep
        fails, we still return RefreshTokenReuseError to the caller.
        """
        try:
            await self._store.revoke_all_for_session(old_record.session_id)

            session = await self._sessions.find_by_id(old_record.session_id)
            if session is not None:
                session.revoke_due_to_token_reuse(reused_token_hash_prefix=hash_prefix)
                await self._sessions.save(session)
        except Exception:
            logger.exception(
                "Failed to fully revoke session after token reuse detection",
                extra={
                    "session_id": str(old_record.session_id),
                    "user_id": str(old_record.user_id),
                    "hash_prefix": hash_prefix,
                },
            )

        logger.warning(
            "Refresh token reuse detected — session revoked",
            extra={
                "session_id": str(old_record.session_id),
                "user_id": str(old_record.user_id),
                "reused_hash_prefix": hash_prefix,
            },
        )
