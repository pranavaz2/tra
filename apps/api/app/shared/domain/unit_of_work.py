"""
Unit of Work — shared kernel Protocol.

Defines the transactional boundary for application-layer use cases.
All repository mutations within a single UoW instance are committed
atomically. If any step fails, the UoW is rolled back.

Usage pattern (explicit commit):
    async with unit_of_work as uow:
        await repo_a.save(entity_a)
        await repo_b.save(entity_b)
        await uow.commit()        # all writes land or none do
    # On exception: __aexit__ calls rollback(); exception propagates

Contract:
  - __aenter__ returns self (the same UoW, not a copy).
  - __aexit__ calls rollback() when exc_type is not None (exception path).
  - __aexit__ is a no-op when exc_type is None (caller committed explicitly).
  - commit() and rollback() are idempotent within a single context.
  - Implementations MUST NOT commit automatically in __aexit__ — the caller
    always commits explicitly. This prevents silent partial commits.

Production implementation (PostgreSQL):
  __aenter__ → BEGIN (acquire AsyncSession from pool)
  commit()   → COMMIT; release session
  rollback() → ROLLBACK; release session
  __aexit__ with exception → rollback()
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, runtime_checkable


@runtime_checkable
class UnitOfWork(Protocol):
    """
    Transactional boundary for application use cases.

    All concrete implementations provide the same context-manager contract.
    The infrastructure layer provides a PostgreSQL-backed implementation
    (wrapping SQLAlchemy AsyncSession). The in-memory implementation is
    used for development and unit tests.
    """

    async def __aenter__(self) -> "UnitOfWork":
        """Enter the transactional context. Returns self."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        """
        Exit the context.

        Calls rollback() if exc_type is not None (exception path).
        Returns False to not suppress the exception.
        """
        ...

    async def commit(self) -> None:
        """Commit all mutations made within this context."""
        ...

    async def rollback(self) -> None:
        """Roll back all mutations made within this context."""
        ...
