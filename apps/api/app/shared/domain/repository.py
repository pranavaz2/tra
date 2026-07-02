"""
Travix AI — Repository Interface

Defines the generic contract for data access. Repository implementations
live in the infrastructure layer (module/repository.py). The domain and
application layers depend on this interface only, never on SQLAlchemy.

Design:
  - Protocol (structural typing) rather than ABC — implementations are
    not required to inherit from this class, only to match the signature.
    This avoids coupling the infrastructure layer to the domain.
  - All methods are async — consistent with the application's async-first stance.
  - Generic in entity type E and identifier type ID.
  - find_by_id returns E | None (not Optional — use the type union directly).
  - save handles both insert and update (upsert semantics; the repository
    determines whether to INSERT or UPDATE based on the entity state).

Usage — defining a concrete repository interface for a module:
    from uuid import UUID
    from app.shared.domain.repository import Repository
    from app.modules.trips.domain.trip import Trip

    class TripRepository(Repository[Trip, UUID], Protocol):
        async def find_by_owner(self, owner_id: UUID) -> list[Trip]: ...

Usage — implementing in the infrastructure layer:
    class SQLAlchemyTripRepository:
        def __init__(self, session: AsyncSession) -> None:
            self._session = session

        async def find_by_id(self, id: UUID) -> Trip | None: ...
        async def save(self, entity: Trip) -> None: ...
        async def delete(self, id: UUID) -> None: ...
        async def exists(self, id: UUID) -> bool: ...
        async def find_by_owner(self, owner_id: UUID) -> list[Trip]: ...
"""

from __future__ import annotations

from typing import Generic, Protocol, TypeVar, runtime_checkable

E = TypeVar("E")
ID = TypeVar("ID")


@runtime_checkable
class Repository(Protocol[E, ID]):
    """
    Generic async repository contract.

    E  — the entity type managed by this repository.
    ID — the type of the entity's primary identifier (typically UUID).
    """

    async def find_by_id(self, id: ID) -> E | None:
        """
        Return the entity with the given ID, or None if not found.

        Never raises NotFoundError — that is the caller's responsibility.
        """
        ...

    async def save(self, entity: E) -> None:
        """
        Persist the entity (insert or update).

        Raises:
            InfrastructureError: If the database operation fails.
        """
        ...

    async def delete(self, id: ID) -> None:
        """
        Remove the entity with the given ID.

        Silently succeeds if the entity does not exist.

        Raises:
            InfrastructureError: If the database operation fails.
        """
        ...

    async def exists(self, id: ID) -> bool:
        """Return True if an entity with the given ID exists."""
        ...
