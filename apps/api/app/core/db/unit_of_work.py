"""
Travix AI — Unit of Work

The Unit of Work (UoW) pattern groups one or more repository operations
into a single atomic transaction. Either all succeed (``commit()``) or all
fail (``rollback()``), maintaining database consistency.

Why UoW alongside the existing ``get_db_session`` dependency?
  - ``get_db_session`` is the standard path for single-operation route
    handlers. It auto-commits on success and auto-rolls back on exception.
  - UoW is for use cases that span multiple aggregates and need explicit
    control over the commit boundary — e.g., creating a trip AND publishing
    a domain event AND sending a notification, all in one transaction.
  - ARQ background workers have no FastAPI DI. They instantiate
    ``SQLAlchemyUnitOfWork`` directly from ``get_session_factory()``.

Interfaces:
  - ``UnitOfWork`` — ``@runtime_checkable Protocol`` for type-checking and
    mocking in tests.
  - ``SQLAlchemyUnitOfWork`` — concrete SQLAlchemy implementation. Manages
    its own ``AsyncSession`` lifecycle within the async context manager.

Usage — in a use case:

    from app.core.db.unit_of_work import SQLAlchemyUnitOfWork
    from app.database import get_session_factory

    class CreateTripUseCase:
        def __init__(self, session_factory) -> None:
            self._session_factory = session_factory

        async def execute(self, payload: TripCreateRequest) -> Trip:
            async with SQLAlchemyUnitOfWork(self._session_factory) as uow:
                trip_repo = TripRepository(uow.session)
                trip = Trip(title=payload.title, ...)
                await trip_repo.save(trip)
                await uow.commit()
                return trip

Usage — in tests (inject a pre-built session):

    # tests override the factory to use the test connection/transaction.
    from app.core.db.unit_of_work import SQLAlchemyUnitOfWork

    async def test_create_trip(db_session_factory):
        async with SQLAlchemyUnitOfWork(db_session_factory) as uow:
            repo = TripRepository(uow.session)
            ...

Nested transactions:
  Call ``uow.begin_nested()`` to create a SAVEPOINT within the outer
  transaction. Useful when a sub-operation should be rolled back
  independently while the outer transaction proceeds:

      async with uow:
          await uow.begin_nested()
          try:
              await notification_repo.record_attempt(...)
              await uow.commit()   # releases the savepoint
          except Exception:
              await uow.rollback_to_savepoint()  # rolls back to savepoint only
          await trip_repo.save(trip)
          await uow.commit()       # commits the outer transaction

  See ``begin_nested()`` and ``rollback_to_savepoint()`` methods below.
"""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction, async_sessionmaker

logger = logging.getLogger(__name__)


@runtime_checkable
class UnitOfWork(Protocol):
    """
    Demarcates a transaction boundary.

    The ``session`` property provides access to the underlying ``AsyncSession``
    for constructing repository instances within the transaction.
    """

    @property
    def session(self) -> AsyncSession:
        """The async session for this unit of work."""
        ...

    async def __aenter__(self) -> "UnitOfWork":
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        ...

    async def commit(self) -> None:
        """Commit the current transaction."""
        ...

    async def rollback(self) -> None:
        """Roll back the current transaction."""
        ...


class SQLAlchemyUnitOfWork:
    """
    SQLAlchemy implementation of the Unit of Work pattern.

    Manages the full session lifecycle: creation, commit/rollback, and close.
    Each instance of this class represents a single transaction scope.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._savepoint: AsyncSessionTransaction | None = None

    @property
    def session(self) -> AsyncSession:
        """The underlying AsyncSession. Only valid within an async with block."""
        if self._session is None:
            raise RuntimeError(
                "SQLAlchemyUnitOfWork.session accessed outside of async context manager. "
                "Use 'async with uow:' before accessing uow.session."
            )
        return self._session

    async def __aenter__(self) -> "SQLAlchemyUnitOfWork":
        self._session = self._session_factory()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
                logger.debug(
                    "UnitOfWork rolled back due to exception",
                    extra={"exception": exc_type.__name__},
                )
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def commit(self) -> None:
        """
        Commit all pending changes in the current transaction.

        After commit, the session's identity map is expired (SQLAlchemy default)
        so subsequent access to attributes will re-fetch from the database.
        This is intentional — it prevents stale reads after a commit boundary.
        ``expire_on_commit=False`` is set in the session factory so ORM objects
        remain accessible after commit without triggering lazy loads.
        """
        await self.session.commit()

    async def rollback(self) -> None:
        """Roll back the current transaction, discarding all pending changes."""
        await self.session.rollback()

    async def begin_nested(self) -> AsyncSessionTransaction:
        """
        Create a SAVEPOINT (nested transaction) within the current transaction.

        Returns the savepoint transaction object. Call ``await savepoint.commit()``
        to release the savepoint or ``await savepoint.rollback()`` to roll back
        to the savepoint without affecting the outer transaction.

        Usage:
            async with uow:
                savepoint = await uow.begin_nested()
                try:
                    await some_risky_operation(uow.session)
                    await savepoint.commit()
                except SomeKnownError:
                    await savepoint.rollback()
                # outer transaction continues
                await uow.commit()
        """
        self._savepoint = await self.session.begin_nested()
        return self._savepoint
