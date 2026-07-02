"""
InMemoryAuthRepository — dev/test implementation of AuthenticationRepository.

Stores AuthenticationCredential aggregates in a process-local dict indexed
by both UserId and normalised email. Used for local development, unit tests,
and integration tests that don't need a real PostgreSQL instance.

IMPORTANT PRODUCTION NOTES:
  1. State is lost on server restart.
  2. Thread/process safety: Python dict reads under the GIL are safe for
     single-key access. Concurrent writes (same email race) are NOT protected
     here — production uses a PostgreSQL UNIQUE constraint on the email column.
  3. Replace this with a PostgreSQL-backed implementation when TASK-2.8
     (Login) adds the Alembic migration for the credentials table.

See ADR-005 for the production migration plan.
"""

from __future__ import annotations

from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.user_id import UserId


class InMemoryAuthRepository:
    """
    In-process AuthenticationRepository for local development and unit tests.

    Maintains two indexes:
      _by_user_id  — keyed by str(UserId)
      _by_email    — keyed by normalised email string

    Both indexes always point to the same AuthenticationCredential object.
    """

    def __init__(self) -> None:
        self._by_user_id: dict[str, AuthenticationCredential] = {}
        self._by_email: dict[str, AuthenticationCredential] = {}

    async def find_by_email(self, email: Email) -> AuthenticationCredential | None:
        return self._by_email.get(str(email))

    async def find_by_user_id(self, user_id: UserId) -> AuthenticationCredential | None:
        return self._by_user_id.get(str(user_id))

    async def save(self, credential: AuthenticationCredential) -> None:
        key_id = str(credential.user_id)
        key_email = str(credential.email)
        self._by_user_id[key_id] = credential
        self._by_email[key_email] = credential

    async def exists_with_email(self, email: Email) -> bool:
        return str(email) in self._by_email

    # ---------------------------------------------------------------------- #
    # Test helpers (not part of AuthenticationRepository Protocol)            #
    # ---------------------------------------------------------------------- #

    def count(self) -> int:
        """Total stored credentials. For diagnostics and tests only."""
        return len(self._by_user_id)

    def clear(self) -> None:
        """Remove all credentials. For test teardown only."""
        self._by_user_id.clear()
        self._by_email.clear()
