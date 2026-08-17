"""Media presentation schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):  # noqa: UP046
    """Standard success data envelope wrapper."""

    data: T
    model_config = ConfigDict(populate_by_name=True)


# ──────────────────────────────────────────────────────────────────────────── #
# Request schemas                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


class MediaCaptionUpdateRequest(BaseModel):
    """Request schema for updating a media caption."""

    caption: str | None = Field(
        None,
        max_length=500,
        description="Text description of the media item. Max 500 characters.",
    )

    model_config = ConfigDict(extra="forbid")


class AttachActivityRequest(BaseModel):
    """Request schema for attaching media to an activity."""

    activity_id: str = Field(
        ...,
        description="The ID of the itinerary activity (ItineraryItemId) to link.",
    )

    model_config = ConfigDict(extra="forbid")


class AttachExpenseRequest(BaseModel):
    """Request schema for attaching media to a budget expense."""

    expense_id: str = Field(
        ...,
        description="The ID of the expense entry to link.",
    )

    model_config = ConfigDict(extra="forbid")


# ──────────────────────────────────────────────────────────────────────────── #
# Response schemas                                                                #
# ──────────────────────────────────────────────────────────────────────────── #


class MediaItemResponse(BaseModel):
    """Response schema representing a single MediaItem."""

    media_id: str
    collection_id: str
    url: str
    media_type: str
    status: str
    mime_type: str
    size_bytes: int
    file_name: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    caption: str | None = None
    uploaded_by: str
    activity_id: str | None = None
    expense_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class MediaListResponse(BaseModel):
    """Paginated list of media items response."""

    items: tuple[MediaItemResponse, ...]
    next_cursor: str | None = None
    has_more: bool
    limit: int

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
