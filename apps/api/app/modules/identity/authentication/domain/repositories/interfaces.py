"""
Authentication Domain Repository Interfaces.

These Protocols define the data-access contract that the domain requires.
The infrastructure layer implements them using SQLAlchemy + PostgreSQL.

Design decisions:
  - All methods are async — the domain interface reflects async-first I/O.
  - Parameters and return types use domain value objects and entities only.
    No SQLAlchemy, no UUIDs-as-strings, no raw dicts cross this boundary.
  - @runtime_checkable enables isinstance() checks in application tests that
    verify injected repositories satisfy the interface.
  - The repository does NOT commit — commit is the caller's responsibility
    (via UnitOfWork in the application layer).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.entities.refresh_token_record import (
    RefreshTokenRecord,
)
from app.modules.identity.authentication.domain.entities.session import AuthenticationSession
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import (
    RefreshTokenId,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


@runtime_checkable
class AuthenticationRepository(Protocol):
    """
    Persistence interface for AuthenticationCredential aggregates.

    One credential per user — the email is a natural unique key.
    Implementations must enforce this uniqueness at the database level.
    """

    async def find_by_email(self, email: Email) -> AuthenticationCredential | None:
        """
        Return the credential for the given normalised email, or None.

        Uses the normalised (lowercase) form for lookup. The Email value
        object ensures normalisation before this method is called.
        """
        ...

    async def find_by_user_id(self, user_id: UserId) -> AuthenticationCredential | None:
        """Return the credential for the given user, or None."""
        ...

    async def save(self, credential: AuthenticationCredential) -> None:
        """
        Persist a new or updated credential.

        Implementations must flush to the database within the current
        transaction but must NOT commit — the caller controls the boundary.
        """
        ...

    async def exists_with_email(self, email: Email) -> bool:
        """
        Return True if any active credential has the given email.

        Used during registration to enforce email uniqueness before
        creating the aggregate (fail-fast, avoids loading the full entity).
        """
        ...


@runtime_checkable
class SessionRepository(Protocol):
    """
    Persistence interface for AuthenticationSession aggregates.

    A user may have multiple concurrent sessions (subject to the
    SessionPolicy.max_concurrent_sessions limit).
    """

    async def find_by_id(self, session_id: SessionId) -> AuthenticationSession | None:
        """Return the session with the given id, or None."""
        ...

    async def find_by_user_id(self, user_id: UserId) -> list[AuthenticationSession]:
        """
        Return all sessions for the given user (including expired and revoked).

        Callers that only want active sessions should filter with
        ActiveSessionSpecification after loading.
        """
        ...

    async def find_by_refresh_token(
        self,
        refresh_token_id: RefreshTokenId,
    ) -> AuthenticationSession | None:
        """
        Return the session that currently holds the given refresh token, or None.

        The infrastructure layer stores refresh_token_id as a column and
        looks it up directly. If this returns None for a token the client
        claims to have, it indicates reuse of a superseded token.
        """
        ...

    async def save(self, session: AuthenticationSession) -> None:
        """
        Persist a new or updated session.

        Must flush within the current transaction but not commit.
        """
        ...

    async def delete(self, session_id: SessionId) -> None:
        """
        Hard-delete a session record.

        Sessions are security infrastructure — hard delete is intentional.
        Expired/revoked sessions are cleaned up by the background job.
        """
        ...

    async def delete_all_for_user(self, user_id: UserId) -> None:
        """
        Hard-delete all session records for the given user.

        Used on logout-all-devices and on RefreshTokenReuseError (stolen
        token detection) to invalidate the entire session family.
        """
        ...


@runtime_checkable
class RefreshTokenRepository(Protocol):
    """
    Persistence interface for RefreshTokenRecord entities.

    One record per issued token. On each rotation, the old record is
    marked ROTATED and a new ACTIVE record is inserted atomically.

    Production implementations must ensure rotate() is fully atomic
    (PostgreSQL: single transaction with SELECT ... FOR UPDATE).
    """

    async def find_by_hash(
        self, token_hash: RefreshTokenHash
    ) -> RefreshTokenRecord | None:
        """
        Look up a token record by its SHA-256 hash.

        Returns None if no record exists for this hash — the caller should
        treat this as an invalid / never-issued token.
        """
        ...

    async def find_by_id(
        self, record_id: RefreshTokenId
    ) -> RefreshTokenRecord | None:
        """Return the record with the given ID, or None."""
        ...

    async def find_active_by_session(
        self, session_id: SessionId
    ) -> RefreshTokenRecord | None:
        """
        Return the single ACTIVE record for the given session, or None.

        At any point in time a session has at most one ACTIVE refresh token.
        """
        ...

    async def find_all_by_session(
        self, session_id: SessionId
    ) -> list[RefreshTokenRecord]:
        """
        Return all records (any state) for the given session.

        Useful for audit and cleanup operations.
        """
        ...

    async def save(self, record: RefreshTokenRecord) -> None:
        """
        Persist a new or updated record.

        Must flush within the current transaction but not commit.
        """
        ...

    async def rotate(
        self,
        *,
        old_hash: RefreshTokenHash,
        new_record: RefreshTokenRecord,
    ) -> None:
        """
        Atomically supersede old_hash's record and insert new_record.

        Within a single atomic unit (lock or database transaction):
          1. Re-validate that old_hash's record is still ACTIVE.
          2. Transition old record to ROTATED.
          3. Persist new_record with status ACTIVE.

        Raises:
            RefreshTokenReuseError    if old record is already ROTATED
                                      (concurrent rotation or stolen-token reuse).
            RefreshTokenNotFoundError if old record no longer exists.
            RefreshTokenRevokedError  if old record is REVOKED.
            RefreshTokenExpiredError  if old record is EXPIRED.

        This method is the primary defence against concurrent-refresh races.
        PostgreSQL implementations must use SELECT FOR UPDATE within a
        SERIALIZABLE (or READ COMMITTED + FOR UPDATE SKIP LOCKED) transaction.
        """
        ...

    async def revoke_all_for_session(self, session_id: SessionId) -> int:
        """
        Revoke all non-terminal records for the given session.

        Returns the count of records transitioned to REVOKED.
        Used on logout and on reuse detection (full session sweep).
        """
        ...

    async def revoke_all_for_user(self, user_id: UserId) -> int:
        """
        Revoke all non-terminal records for all of the user's sessions.

        Returns the count of records transitioned to REVOKED.
        Used on password change and account compromise response.
        """
        ...
