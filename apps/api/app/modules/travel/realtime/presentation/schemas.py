"""Real-Time Presentation Layer — Pydantic Schemas."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class CollaboratorPresenceSchema(BaseModel):
    """Schema representing an active collaborator in a trip."""

    user_id: str
    display_name: str
    role: str
    joined_at: str
    client_id: str


class PresenceSyncPayload(BaseModel):
    """Payload sent upon initial WebSocket connection."""

    collaborators: list[CollaboratorPresenceSchema] = Field(default_factory=list)
    connection_id: str


class RealtimeEventSchema(BaseModel):
    """Envelope for all WebSocket messages and domain events."""

    event_id: str
    trip_id: str
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    version: int | None = None
    actor_id: str | None = None
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)
