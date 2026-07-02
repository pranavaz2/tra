"""
Travix AI — Generic SQLAlchemy Repository

Infrastructure-side implementation of the Repository Protocol defined in
``app.shared.domain.repository``.

This module provides a single generic base class ``SQLAlchemyRepository[E, IDT]``
that feature repositories extend. It handles the common CRUD operations so
feature repositories focus only on domain-specific queries.

Architecture:
  - The shared kernel defines the INTERFACE (``Repository`` Protocol in domain).
  - This module provides the IMPLEMENTATION (infrastructure layer).
  - Feature modules subclass ``SQLAlchemyRepository`` and add module-specific
    query methods.

Usage — defining a feature repository:

    from uuid import UUID
    from app.core.db.repository import SQLAlchemyRepository
    from app.modules.trips.models import TripModel

    class TripRepository(SQLAlchemyRepository[TripModel, UUID]):
        def __init__(self, session: AsyncSession) -> None:
            super().__init__(session, TripModel)

        async def find_by_owner(self, owner_id: UUID) -> list[TripModel]:
            stmt = (
                select(TripModel)
                .where(TripModel.owner_id == owner_id)
                .where(TripModel.deleted_at.is_(None))
                .order_by(TripModel.created_at.desc())
            )
            result = await self._session.execute(stmt)
            return list(result.scalars())

Usage — in a route handler via dependency injection:

    @router.get("/trips/{trip_id}")
    async def get_trip(
        trip_id: UUID,
        db: DatabaseSession,
    ) -> TripResponse:
        repo = TripRepository(db)
        trip = await repo.find_by_id(trip_id)
        if trip is None:
            raise TripNotFoundError(trip_id)
        return TripResponse.model_validate(trip)

Session management:
  The repository does NOT own the session. The session lifecycle is managed
  by the FastAPI dependency (``get_db_session``) or the ``SQLAlchemyUnitOfWork``.
  The repository only uses the session — it never commits, rolls back, or closes it.

``save()`` calls ``session.flush()`` (not ``session.commit()``):
  This writes the change to the database within the current transaction but
  does NOT commit. This allows the caller (route handler or UoW) to control
  when the transaction is committed. It also makes the new ID available before
  the commit, enabling event dispatch or downstream operations in the same
  transaction.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

# E is bounded to DeclarativeBase — SQLAlchemy ORM model classes.
# This avoids importing app.database.Base which would create a circular import.
E = TypeVar("E", bound=DeclarativeBase)
IDT = TypeVar("IDT")


class SQLAlchemyRepository(Generic[E, IDT]):
    """
    Generic async repository backed by SQLAlchemy AsyncSession.

    Type parameters:
      E   — The SQLAlchemy ORM model class (also the domain entity in this codebase).
      IDT — The primary key type (typically ``uuid.UUID``).

    Feature repositories extend this class and inject the concrete model:

        class TripRepository(SQLAlchemyRepository[TripModel, UUID]):
            def __init__(self, session: AsyncSession) -> None:
                super().__init__(session, TripModel)
    """

    def __init__(self, session: AsyncSession, model_class: type[E]) -> None:
        self._session = session
        self._model = model_class

    # ------------------------------------------------------------------ #
    # Core Repository Protocol methods                                     #
    # ------------------------------------------------------------------ #

    async def find_by_id(self, id: IDT) -> E | None:
        """
        Return the entity with the given primary key, or None if not found.

        Uses ``session.get()`` which checks the session's identity map before
        hitting the database — effectively free on repeated access within the
        same request.
        """
        return await self._session.get(self._model, id)

    async def save(self, entity: E) -> None:
        """
        Persist the entity (INSERT on new, UPDATE on existing).

        SQLAlchemy determines insert vs. update based on whether the instance
        is already tracked in the session's identity map (i.e., has a PK that
        exists in the database).

        Calls ``flush()`` to write to the database within the current transaction
        so that generated columns (e.g., ``created_at``) are populated on the
        entity immediately after the call.
        """
        self._session.add(entity)
        await self._session.flush([entity])

    async def delete(self, id: IDT) -> None:
        """
        Remove the entity with the given primary key.

        Silently succeeds if the entity does not exist (idempotent).
        Calls ``flush()`` so the DELETE is sent to the database immediately
        within the current transaction.

        Note: For soft-delete, feature repositories should OVERRIDE this method
        to set ``deleted_at`` instead of issuing a hard DELETE:

            async def delete(self, id: UUID) -> None:
                trip = await self.find_by_id(id)
                if trip is not None:
                    trip.deleted_at = datetime.now(UTC)
                    await self._session.flush([trip])
        """
        entity = await self.find_by_id(id)
        if entity is not None:
            await self._session.delete(entity)
            await self._session.flush()

    async def exists(self, id: IDT) -> bool:
        """
        Return True if an entity with the given primary key exists.

        Uses ``session.get()`` — benefits from identity map cache on repeated
        checks within the same session. Feature repositories may override this
        with a lighter ``SELECT EXISTS(...)`` for performance-critical paths.
        """
        entity = await self._session.get(self._model, id)
        return entity is not None

    # ------------------------------------------------------------------ #
    # Convenience extensions beyond the base Protocol                      #
    # ------------------------------------------------------------------ #

    async def count(self) -> int:
        """Return the total row count in the model's table (all rows, including deleted)."""
        stmt = select(func.count()).select_from(self._model)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def find_all(self, *, limit: int = 100, offset: int = 0) -> list[E]:
        """
        Return up to ``limit`` rows with ``offset`` for simple offset pagination.

        Prefer cursor-based pagination (``app.core.db.query.paginate()``) for
        production collection endpoints. This method is intended for test setup
        and administrative tools.
        """
        stmt = select(self._model).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def save_all(self, entities: list[E]) -> None:
        """
        Persist multiple entities in a single flush.

        More efficient than calling ``save()`` repeatedly because it defers all
        flush work to a single round-trip.
        """
        for entity in entities:
            self._session.add(entity)
        await self._session.flush(entities)
