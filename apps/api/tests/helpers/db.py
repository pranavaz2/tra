"""
Travix AI — Database Test Helpers

Utility functions and classes for writing repository and database integration
tests. Import these in integration test files rather than duplicating boilerplate.

Usage:
    from tests.helpers.db import count_rows, exists_by_id, flush_and_refresh

    async def test_create_trip(db_session):
        trip = TripModel(id=uuid4(), title="Test Trip", ...)
        db_session.add(trip)
        await db_session.flush()

        assert await count_rows(db_session, TripModel) == 1
        assert await exists_by_id(db_session, TripModel, trip.id)

    async def test_soft_delete(db_session):
        trip = TripModel(...)
        db_session.add(trip)
        await db_session.flush()

        await soft_delete(db_session, trip)
        assert trip.is_deleted
        assert await count_active(db_session, TripModel) == 0
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

E = TypeVar("E")


# ---------------------------------------------------------------------------
# Row counts
# ---------------------------------------------------------------------------


async def count_rows(session: AsyncSession, model: type[E]) -> int:
    """
    Return the total row count in ``model``'s table, including soft-deleted rows.

    Use this in tests to assert the exact number of rows after an operation.
    """
    result = await session.execute(select(func.count()).select_from(model))
    return result.scalar_one()


async def count_active(session: AsyncSession, model: type[E]) -> int:
    """
    Return the active (non-deleted) row count for models using SoftDeleteMixin.

    Requires the model to have a ``deleted_at`` column.
    """
    result = await session.execute(
        select(func.count()).select_from(model).where(model.deleted_at.is_(None))  # type: ignore[attr-defined]
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Existence checks
# ---------------------------------------------------------------------------


async def exists_by_id(session: AsyncSession, model: type[E], id: Any) -> bool:
    """
    Return True if a row with the given primary key exists in ``model``'s table.

    Checks the session identity map first (no DB hit for already-loaded entities).
    """
    entity = await session.get(model, id)
    return entity is not None


# ---------------------------------------------------------------------------
# Session utilities
# ---------------------------------------------------------------------------


async def flush_and_refresh(session: AsyncSession, entity: E) -> E:
    """
    Flush pending changes and refresh the entity from the database.

    Use this when you need to verify server-generated column values
    (e.g., ``created_at``, ``updated_at``) after an INSERT.

    Returns the refreshed entity.
    """
    await session.flush([entity])
    await session.refresh(entity)
    return entity


# ---------------------------------------------------------------------------
# Soft-delete helper
# ---------------------------------------------------------------------------


async def soft_delete(session: AsyncSession, entity: Any) -> None:
    """
    Mark an entity as soft-deleted by setting ``deleted_at`` to now (UTC).

    Requires the entity to use ``SoftDeleteMixin``.
    Flushes the change to the database within the current transaction.
    """
    entity.deleted_at = datetime.now(UTC)
    await session.flush([entity])


# ---------------------------------------------------------------------------
# Repository test base
# ---------------------------------------------------------------------------


class RepositoryTestCase:
    """
    Base class providing common assertions for repository integration tests.

    Subclass this to get consistent assertion helpers across all repository
    test files:

        class TestTripRepository(RepositoryTestCase):
            async def test_save_and_find(self, db_session):
                repo = TripRepository(db_session)
                trip = TripModel(id=uuid4(), ...)
                await repo.save(trip)
                found = await repo.find_by_id(trip.id)
                self.assert_entity_equal(trip, found)
    """

    @staticmethod
    def assert_entity_equal(expected: Any, actual: Any | None) -> None:
        """Assert that ``actual`` is not None and matches ``expected`` by id."""
        assert actual is not None, "Expected entity to exist but got None"
        assert actual.id == expected.id, (
            f"Entity id mismatch: expected {expected.id!r}, got {actual.id!r}"
        )

    @staticmethod
    def assert_is_soft_deleted(entity: Any) -> None:
        """Assert that ``entity`` has been soft-deleted (deleted_at is not None)."""
        assert hasattr(entity, "deleted_at"), "Entity does not have deleted_at (SoftDeleteMixin)"
        assert entity.deleted_at is not None, "Expected entity to be soft-deleted but deleted_at is None"

    @staticmethod
    def assert_is_not_deleted(entity: Any) -> None:
        """Assert that ``entity`` has NOT been soft-deleted."""
        assert hasattr(entity, "deleted_at"), "Entity does not have deleted_at (SoftDeleteMixin)"
        assert entity.deleted_at is None, (
            f"Expected entity to be active but deleted_at={entity.deleted_at!r}"
        )

    @staticmethod
    def assert_timestamps_set(entity: Any) -> None:
        """Assert that created_at and updated_at are populated (TimestampMixin)."""
        assert hasattr(entity, "created_at"), "Entity missing created_at (TimestampMixin)"
        assert hasattr(entity, "updated_at"), "Entity missing updated_at (TimestampMixin)"
        assert entity.created_at is not None, "created_at should not be None after flush"
        assert entity.updated_at is not None, "updated_at should not be None after flush"
