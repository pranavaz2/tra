"""In-Memory ProposedAction Repository Implementation."""

from __future__ import annotations

import asyncio
from app.modules.travel.assistant.domain.entities.proposed_action import ProposedAction
from app.modules.travel.assistant.domain.enums import ActionStatus
from app.modules.travel.assistant.domain.repositories.interfaces import (
    IProposedActionRepository,
)
from app.modules.travel.assistant.domain.value_objects import ActionId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class InMemoryProposedActionRepository(IProposedActionRepository):
    """In-memory storage for AI proposed actions."""

    def __init__(self) -> None:
        self._actions: dict[str, ProposedAction] = {}
        self._lock = asyncio.Lock()

    async def save(self, action: ProposedAction) -> None:
        async with self._lock:
            self._actions[str(action.entity_id)] = action

    async def find_by_id(self, action_id: ActionId) -> ProposedAction | None:
        async with self._lock:
            return self._actions.get(str(action_id))

    async def find_pending_by_trip_id(self, trip_id: TripId) -> list[ProposedAction]:
        async with self._lock:
            return [
                a
                for a in self._actions.values()
                if a.trip_id == trip_id and a.status == ActionStatus.PENDING
            ]
