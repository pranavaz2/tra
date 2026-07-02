"""
InMemoryRefreshTokenStore — dev/test implementation of RefreshTokenRepository.

Stores all RefreshTokenRecord objects in process memory using two dict indexes:
  _by_hash: RefreshTokenHash.value → RefreshTokenRecord
  _by_id:   str(RefreshTokenId)   → RefreshTokenRecord

Thread safety:
  All mutations use asyncio.Lock to prevent concurrent-rotation races within
  a single event loop. This is safe for a single-process FastAPI application.

IMPORTANT PRODUCTION NOTES:
  1. State is lost on server restart — use PostgreSQL for production.
  2. asyncio.Lock does NOT protect across multiple processes or servers.
     Production must use SELECT ... FOR UPDATE within a database transaction.
  3. The rotate() method is the critical atomic section. PostgreSQL
     implementations must use SERIALIZABLE isolation or FOR UPDATE SKIP LOCKED.

See ADR-005 §Rotation Atomicity for the production migration plan.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.entities.refresh_token_record import (
    RefreshTokenRecord,
    TokenState,
)
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.errors import (
    RefreshTokenExpiredError,
    RefreshTokenNotFoundError,
    RefreshTokenReuseError,
    RefreshTokenRevokedError,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import RefreshTokenId
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId

logger = logging.getLogger(__name__)


class InMemoryRefreshTokenStore:
    """
    In-process RefreshTokenRepository for local development and unit tests.

    NOT for production use. See module docstring for limitations.

    Every store instance has its own lock and data — create one shared instance
    per application process and register it via the DI factory.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Primary index: hash string → record (used for client token lookup)
        self._by_hash: dict[str, RefreshTokenRecord] = {}
        # Secondary index: record_id string → record (used for ID-based lookup)
        self._by_id: dict[str, RefreshTokenRecord] = {}

    # ------------------------------------------------------------------ #
    # Read operations (lock-free for reads — Python dict reads are safe   #
    # under the GIL for single-key access; no structural mutation)        #
    # ------------------------------------------------------------------ #

    async def find_by_hash(
        self, token_hash: RefreshTokenHash
    ) -> RefreshTokenRecord | None:
        """Look up by SHA-256 hash (the primary lookup path for client tokens)."""
        return self._by_hash.get(token_hash.value)

    async def find_by_id(
        self, record_id: RefreshTokenId
    ) -> RefreshTokenRecord | None:
        """Look up by record UUID."""
        return self._by_id.get(str(record_id))

    async def find_active_by_session(
        self, session_id: SessionId
    ) -> RefreshTokenRecord | None:
        """Return the ACTIVE record for the session, or None."""
        return next(
            (
                r
                for r in self._by_id.values()
                if r.session_id == session_id and r.status == TokenState.ACTIVE
            ),
            None,
        )

    async def find_all_by_session(
        self, session_id: SessionId
    ) -> list[RefreshTokenRecord]:
        """Return all records (any state) for the session."""
        return [r for r in self._by_id.values() if r.session_id == session_id]

    # ------------------------------------------------------------------ #
    # Write operations (lock required for all mutations)                   #
    # ------------------------------------------------------------------ #

    async def save(self, record: RefreshTokenRecord) -> None:
        """Upsert a record into both indexes."""
        async with self._lock:
            self._by_hash[record.token_hash.value] = record
            self._by_id[str(record.entity_id)] = record

    async def rotate(
        self,
        *,
        old_hash: RefreshTokenHash,
        new_record: RefreshTokenRecord,
    ) -> None:
        """
        Atomic rotation: supersede old_hash's record and insert new_record.

        Holds the asyncio.Lock for the entire operation to prevent concurrent
        rotations from both succeeding with the same old token.

        The re-validation under the lock is the critical invariant:
          - Two concurrent requests presenting the same token race for the lock.
          - The first acquires the lock, sees ACTIVE, marks ROTATED, inserts new.
          - The second acquires the lock, sees ROTATED → raises RefreshTokenReuseError.

        Raises:
            RefreshTokenNotFoundError  if old_hash has no record.
            RefreshTokenReuseError     if old record is already ROTATED.
            RefreshTokenRevokedError   if old record is REVOKED.
            RefreshTokenExpiredError   if old record is EXPIRED (checked by wall clock).
        """
        async with self._lock:
            old = self._by_hash.get(old_hash.value)

            if old is None:
                raise RefreshTokenNotFoundError()

            # Re-validate state under lock — may have changed since the pre-lock check.
            if old.status == TokenState.ROTATED:
                raise RefreshTokenReuseError()
            if old.status == TokenState.REVOKED:
                raise RefreshTokenRevokedError()
            if old.status == TokenState.EXPIRED or datetime.now(UTC) >= old.expires_at:
                raise RefreshTokenExpiredError()

            # Transition old → ROTATED and insert new → ACTIVE.
            old.mark_rotated()
            self._by_hash[old_hash.value] = old
            self._by_id[str(old.entity_id)] = old

            self._by_hash[new_record.token_hash.value] = new_record
            self._by_id[str(new_record.entity_id)] = new_record

        logger.debug(
            "Refresh token rotated",
            extra={
                "old_hash_prefix": old_hash.value[:16],
                "new_record_id": str(new_record.entity_id),
                "session_id": str(new_record.session_id),
                "rotation_counter": new_record.rotation_counter,
            },
        )

    async def revoke_all_for_session(self, session_id: SessionId) -> int:
        """Revoke all non-terminal records for the session. Returns count revoked."""
        count = 0
        async with self._lock:
            for record in self._by_id.values():
                if record.session_id == session_id and not record.is_terminal:
                    record.revoke()
                    count += 1
        return count

    async def revoke_all_for_user(self, user_id: UserId) -> int:
        """Revoke all non-terminal records for all of the user's sessions. Returns count."""
        count = 0
        async with self._lock:
            for record in self._by_id.values():
                if record.user_id == user_id and not record.is_terminal:
                    record.revoke()
                    count += 1
        return count

    # ------------------------------------------------------------------ #
    # Diagnostics (not part of RefreshTokenRepository Protocol)           #
    # ------------------------------------------------------------------ #

    def record_count(self) -> int:
        """Total number of stored records (any state). For tests and diagnostics only."""
        return len(self._by_id)

    def clear(self) -> None:
        """Remove all records. For test teardown only — not safe in production."""
        self._by_hash.clear()
        self._by_id.clear()


# ---------------------------------------------------------------------------
# InMemorySessionRepository (dev/test placeholder)
# ---------------------------------------------------------------------------


class InMemorySessionRepository:
    """
    Minimal in-memory SessionRepository for local development and unit tests.

    Provides just enough functionality for RefreshTokenApplicationService
    to perform rotation. Will be replaced by a PostgreSQL-backed implementation
    in TASK-2.7 (login / registration).

    NOT for production use.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, AuthenticationSession] = {}

    async def find_by_id(self, session_id: SessionId) -> AuthenticationSession | None:
        return self._sessions.get(str(session_id))

    async def find_by_user_id(self, user_id: UserId) -> list[AuthenticationSession]:
        return [s for s in self._sessions.values() if s.user_id == user_id]

    async def find_by_refresh_token(
        self, refresh_token_id: RefreshTokenId
    ) -> AuthenticationSession | None:
        return next(
            (s for s in self._sessions.values() if s.refresh_token_id == refresh_token_id),
            None,
        )

    async def save(self, session: AuthenticationSession) -> None:
        self._sessions[str(session.entity_id)] = session

    async def delete(self, session_id: SessionId) -> None:
        self._sessions.pop(str(session_id), None)

    async def delete_all_for_user(self, user_id: UserId) -> None:
        to_delete = [k for k, s in self._sessions.items() if s.user_id == user_id]
        for k in to_delete:
            del self._sessions[k]

    def add_session(self, session: AuthenticationSession) -> None:
        """Test helper: directly insert a session without going through save()."""
        self._sessions[str(session.entity_id)] = session

    def clear(self) -> None:
        """Remove all sessions. For test teardown only."""
        self._sessions.clear()
