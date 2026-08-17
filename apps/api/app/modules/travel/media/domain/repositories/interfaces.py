"""IMediaCollectionRepository Protocol interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


@runtime_checkable
class IMediaCollectionRepository(Protocol):
    """Persistence interface for TripMediaCollection aggregates."""

    async def find_by_id(self, collection_id: MediaCollectionId) -> TripMediaCollection | None:
        """Find media collection by its primary ID."""
        ...

    async def find_by_trip_id(self, trip_id: TripId) -> TripMediaCollection | None:
        """Find the latest active (non-deleted) media collection for a trip."""
        ...

    async def save(self, collection: TripMediaCollection) -> None:
        """Persist or update a TripMediaCollection aggregate."""
        ...

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Check if a media collection exists for the trip."""
        ...
