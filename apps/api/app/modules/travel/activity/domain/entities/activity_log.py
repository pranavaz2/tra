"""TripActivityLog domain entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from app.modules.travel.activity.domain.enums import ActivityAction


@dataclass(kw_only=True, eq=False)
class TripActivityLog:
    """
    Immutable audit and activity log entry for a trip.

    Records what happened, who did it, and contextual metadata.
    """

    activity_id: uuid.UUID
    trip_id: uuid.UUID
    actor_id: uuid.UUID
    action: ActivityAction
    entity_type: str
    entity_id: str
    title: str
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        trip_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: ActivityAction,
        entity_type: str,
        entity_id: str,
        title: str,
        description: str,
        metadata: dict[str, Any] | None = None,
        activity_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
    ) -> TripActivityLog:
        return cls(
            activity_id=activity_id or uuid.uuid4(),
            trip_id=trip_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            title=title,
            description=description,
            metadata=metadata or {},
            created_at=created_at or datetime.now(UTC),
        )
