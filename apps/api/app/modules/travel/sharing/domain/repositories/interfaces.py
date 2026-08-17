"""ITripCollaborationRepository and IInvitationRepository Protocol interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.travel.sharing.domain.entities.invitation import Invitation
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
from app.modules.travel.sharing.domain.value_objects.collaboration_id import (
    CollaborationId,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


@runtime_checkable
class ITripCollaborationRepository(Protocol):
    """Persistence interface for TripCollaboration aggregates."""

    async def find_by_id(
        self, collaboration_id: CollaborationId
    ) -> TripCollaboration | None:
        """Find collaboration by its primary ID. Returns None if not found."""
        ...

    async def find_by_trip_id(self, trip_id: TripId) -> TripCollaboration | None:
        """Find the active (non-deleted) collaboration for a trip."""
        ...

    async def save(self, collaboration: TripCollaboration) -> None:
        """Persist or update a TripCollaboration aggregate."""
        ...

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Return True if a non-deleted collaboration exists for the trip."""
        ...

    async def find_by_share_token(self, token: str) -> TripCollaboration | None:
        """Find an active, public collaboration by its share token."""
        ...


@runtime_checkable
class IInvitationRepository(Protocol):
    """Persistence interface for Invitation look-ups by token."""

    async def find_by_token(self, token: str) -> Invitation | None:
        """Find a PENDING invitation by its opaque share token."""
        ...
