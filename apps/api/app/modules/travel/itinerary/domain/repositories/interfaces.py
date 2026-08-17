"""IItineraryRepository — domain persistence interface for the Itinerary aggregate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


@runtime_checkable
class IItineraryRepository(Protocol):
    """
    Persistence interface for Itinerary aggregates.

    Implementations:
      - SQLAlchemyItineraryRepository (infrastructure layer) — production.
      - InMemoryItineraryRepository (tests) — used in unit tests.
    """

    async def find_by_id(self, itinerary_id: ItineraryId) -> Itinerary | None:
        """
        Return the Itinerary with the given ID, or None if not found.

        Soft-deleted itineraries ARE returned — callers decide whether to
        reject deleted records.
        """
        ...

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        """
        Return the Itinerary with the given Trip ID, or None if not found.

        Soft-deleted itineraries ARE returned.
        """
        ...

    async def save(self, itinerary: Itinerary) -> None:
        """
        Persist a new or updated itinerary (upsert semantics).

        Must flush to the database within the current transaction but must
        NOT commit — the caller controls the transaction boundary.
        """
        ...

    async def exists(self, itinerary_id: ItineraryId) -> bool:
        """Return True if a (non-deleted) itinerary with this ID exists."""
        ...

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Return True if a (non-deleted) itinerary for this Trip ID exists."""
        ...
