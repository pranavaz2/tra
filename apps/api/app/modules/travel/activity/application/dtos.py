"""Activity application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import uuid

from app.modules.travel.activity.domain.entities.activity_log import TripActivityLog


@dataclass(frozen=True)
class ActivityLogDTO:
    """Read-model representation of a trip activity."""

    activity_id: str
    trip_id: str
    actor_id: str
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_entity(
        cls,
        entity: TripActivityLog,
        actor_name: str | None = None,
    ) -> ActivityLogDTO:
        return cls(
            activity_id=str(entity.activity_id),
            trip_id=str(entity.trip_id),
            actor_id=str(entity.actor_id),
            actor_name=actor_name or f"User {str(entity.actor_id)[:6]}",
            action=entity.action.value,
            entity_type=entity.entity_type,
            entity_id=entity.entity_id,
            title=entity.title,
            description=entity.description,
            metadata=entity.metadata,
            created_at=entity.created_at,
        )


@dataclass(frozen=True)
class ActivityFeedPageDTO:
    """Paginated activity feed response."""

    items: list[ActivityLogDTO]
    total: int
    limit: int
    offset: int
    has_more: bool
