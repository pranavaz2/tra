"""
InMemoryUnitOfWork — dev/test implementation of UnitOfWork.

Provides the async context-manager contract required by the application
layer without a real database transaction. All writes land immediately
in the in-memory repository dicts; commit() and rollback() are state
flags that tests can assert on.

IMPORTANT PRODUCTION NOTES:
  1. There is NO real rollback. Writes to InMemory repositories happen
     immediately and cannot be undone. Tests that need true isolation
     must create fresh repository instances per test.
  2. In production, replace this with PostgresUnitOfWork (future task):
       class PostgresUnitOfWork:
           def __init__(self, session: AsyncSession) -> None: ...
           async def commit(self) -> None: await self._session.commit()
           async def rollback(self) -> None: await self._session.rollback()
           async def __aexit__(self, exc_type, ...):
               if exc_type: await self.rollback()

  3. The asyncio.Lock is NOT required here because in-memory repos use
     their own per-operation locking. The UoW is lock-free.

See TASK-2.7.md §Unit of Work for the production migration plan.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class InMemoryUnitOfWork:
    """
    In-process Unit of Work for local development and unit tests.

    Tracks commit/rollback state so tests can verify the service
    called commit() on success and did not commit on failure.

    Usage in tests:
        uow = InMemoryUnitOfWork()
        service = RegistrationService(..., unit_of_work=uow)
        await service.execute(command)
        assert uow.committed    # verifies happy path
        assert not uow.rolled_back
    """

    def __init__(self) -> None:
        self.committed: bool = False
        self.rolled_back: bool = False

    async def __aenter__(self) -> "InMemoryUnitOfWork":
        self.committed = False
        self.rolled_back = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if exc_type is not None:
            await self.rollback()
        return False  # Never suppress exceptions

    async def commit(self) -> None:
        """Mark the unit of work as committed."""
        self.committed = True
        logger.debug("InMemoryUnitOfWork: committed")

    async def rollback(self) -> None:
        """Mark the unit of work as rolled back. No actual undo for in-memory repos."""
        self.rolled_back = True
        logger.debug("InMemoryUnitOfWork: rolled back (in-memory — no actual undo)")


class SQLAlchemyUnitOfWork:
    """Async SQLAlchemy Unit of Work wrapping an AsyncSession."""

    def __init__(self, session: "AsyncSession") -> None:
        self._session = session

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        if exc_type is not None:
            await self.rollback()
        return False

    async def commit(self) -> None:
        """Commit the session transaction."""
        await self._session.commit()

    async def rollback(self) -> None:
        """Rollback the session transaction."""
        await self._session.rollback()

