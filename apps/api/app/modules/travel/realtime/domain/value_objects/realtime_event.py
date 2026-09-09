"""Trip Realtime Event Value Object."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
import uuid

from app.modules.travel.realtime.domain.enums import (
    EntityActionType,
    EntityType,
    RealtimeEventType,
)
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class TripRealtimeEvent(ValueObject):
    """Immutable event broadcast to all active WebSocket clients on a trip."""

    event_id: str
    trip_id: str
    event_type: str  # RealtimeEventType value or str
    entity_type: str  # EntityType value or str
    entity_id: str
    action: str  # EntityActionType value or str
    version: int | None
    actor_id: str | None
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        trip_id: str,
        event_type: RealtimeEventType | str,
        entity_type: EntityType | str,
        entity_id: str,
        action: EntityActionType | str,
        version: int | None = None,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> TripRealtimeEvent:
        """Construct a new TripRealtimeEvent with UTC timestamp."""
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            trip_id=str(trip_id),
            event_type=event_type.value if isinstance(event_type, RealtimeEventType) else str(event_type),
            entity_type=entity_type.value if isinstance(entity_type, EntityType) else str(entity_type),
            entity_id=str(entity_id),
            action=action.value if isinstance(action, EntityActionType) else str(action),
            version=version,
            actor_id=str(actor_id) if actor_id else None,
            timestamp=datetime.now(UTC).isoformat(),
            payload=payload or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert event to serializable dictionary for WebSocket transmission."""
        return {
            "event_id": self.event_id,
            "trip_id": self.trip_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "version": self.version,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
