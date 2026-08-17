"""
ITripRepository — domain persistence interface for the Trip aggregate.

This Protocol defines what the domain requires from any Trip storage
implementation. It contains no SQL, no SQLAlchemy, and no framework code.

The infrastructure layer provides a concrete SQLAlchemy implementation;
the application layer depends only on this interface via dependency injection.

Design decisions:
  - All methods are async — consistent with the project's async-first stance.
  - Parameters and return types use domain value objects and entities only.
  - @runtime_checkable enables isinstance() checks in tests to verify that
    injected repositories satisfy this interface.
  - The repository does NOT commit — commit is the caller's responsibility
    (application layer via UnitOfWork or FastAPI dependency lifecycle).
  - Paginated queries return (list[Trip], next_cursor | None). Cursor encoding
    (base64url) is an infrastructure and application layer concern — the
    domain receives and returns raw sort-key values (str(TripId)).
  - find_by_id returns Trip | None. The caller raises TripNotFoundError when
    None is returned and a result was required — the repository never raises
    domain errors for absent records.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle


@runtime_checkable
class ITripRepository(Protocol):
    """
    Persistence interface for Trip aggregates.

    Implementations:
      - SQLAlchemyTripRepository (infrastructure layer) — production.
      - InMemoryTripRepository (tests) — used in unit tests.
    """

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        """
        Return the Trip with the given ID, or None if not found.

        Soft-deleted trips ARE returned — callers decide whether to
        reject deleted records based on their use case.
        """
        ...

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: TripId | None = None,
        status_filter: TripStatus | None = None,
    ) -> list[Trip]:
        """
        Return up to limit non-deleted trips owned by owner_id.

        Ordered by created_at descending (newest first).

        Args:
            owner_id:      Filter to this owner's trips.
            limit:         Maximum number of trips to return. Request limit+1
                           to determine whether a next page exists.
            after_id:      Cursor — return trips created before the trip with
                           this ID. None starts from the beginning.
            status_filter: When provided, return only trips in this status.
        """
        ...

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        """
        Return all non-deleted trips accessible to user_id (as owner or
        collaborator) whose status is PLANNED or ACTIVE.

        Used for the "My Trips" home screen — only upcoming/in-progress trips.
        """
        ...

    async def save(self, trip: Trip) -> None:
        """
        Persist a new or updated trip (upsert semantics).

        Must flush to the database within the current transaction but must
        NOT commit — the caller controls the transaction boundary.

        Raises:
            InfrastructureError: if the database operation fails.
        """
        ...

    async def delete(self, trip_id: TripId) -> None:
        """
        Hard-delete the Trip record with the given ID.

        This is the physical record deletion used for data retention and GDPR
        erasure flows. For user-initiated deletion, use Trip.delete() which
        performs a soft delete and emits TripDeleted.

        Silently succeeds if the record does not exist.
        """
        ...

    async def exists(self, trip_id: TripId) -> bool:
        """Return True if a (non-deleted) trip with this ID exists."""
        ...

    async def exists_with_title(
        self,
        owner_id: UserId,
        title: TripTitle,
    ) -> bool:
        """
        Return True if owner_id already has a non-deleted trip with this title.

        Case-insensitive match using the stored normalised title. Used before
        Trip.create() to warn users of potential duplicates — this is not a
        hard uniqueness constraint.
        """
        ...
