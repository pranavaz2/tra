"""ProposedAction Repository Interface."""

from __future__ import annotations

from typing import Protocol

from app.modules.travel.assistant.domain.entities.proposed_action import ProposedAction
from app.modules.travel.assistant.domain.value_objects import ActionId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class IProposedActionRepository(Protocol):
    """Repository interface for persisting and retrieving proposed assistant actions."""

    async def save(self, action: ProposedAction) -> None:
        """Save or update a proposed action."""
        ...

    async def find_by_id(self, action_id: ActionId) -> ProposedAction | None:
        """Find a proposed action by its unique ID."""
        ...

    async def find_pending_by_trip_id(self, trip_id: TripId) -> list[ProposedAction]:
        """Find all pending proposed actions for a trip."""
        ...
