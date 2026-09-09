"""Activity repository interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
import uuid

from app.modules.travel.activity.domain.entities.activity_log import TripActivityLog


@runtime_checkable
class ITripActivityRepository(Protocol):
    """Abstract port for persisting and querying trip activity logs."""

    async def save(self, activity: TripActivityLog) -> None:
        """Persist a single activity log entry."""
        ...

    async def list_by_trip(
        self,
        trip_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TripActivityLog]:
        """List chronological activity logs for a trip (newest first)."""
        ...

    async def count_by_trip(self, trip_id: uuid.UUID) -> int:
        """Count total activity logs for a trip."""
        ...
