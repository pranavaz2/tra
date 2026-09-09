"""Activity presentation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActivityLogResponse(BaseModel):
    """Activity log item response."""

    model_config = ConfigDict(frozen=True)

    activity_id: str = Field(description="Unique activity ID")
    trip_id: str = Field(description="Associated Trip ID")
    actor_id: str = Field(description="User ID of the actor")
    actor_name: str | None = Field(default=None, description="Display name of actor")
    action: str = Field(description="Action name (e.g. day_added, expense_added)")
    entity_type: str = Field(description="Entity type affected")
    entity_id: str = Field(description="ID of affected entity")
    title: str = Field(description="Human-readable title")
    description: str = Field(description="Contextual activity details")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Structured event payload")
    created_at: datetime = Field(description="Timestamp of event")


class ActivityFeedResponse(BaseModel):
    """Paginated activity feed response."""

    model_config = ConfigDict(frozen=True)

    items: list[ActivityLogResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
