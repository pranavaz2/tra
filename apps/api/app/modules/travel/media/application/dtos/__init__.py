"""Media application DTOs and result type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

from app.modules.travel.media.domain.entities.media_item import MediaItem
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.shared.domain.result import Result


@dataclass(frozen=True)
class MediaItemSummary:
    """Summary DTO for a MediaItem."""

    media_id: str
    collection_id: str
    url: str
    media_type: str
    status: str
    mime_type: str
    size_bytes: int
    file_name: str | None
    width: int | None
    height: int | None
    duration_seconds: float | None
    caption: str | None
    uploaded_by: str
    activity_id: str | None
    expense_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entity(cls, item: MediaItem) -> MediaItemSummary:
        return cls(
            media_id=str(item.entity_id),
            collection_id=str(item.collection_id),
            url=str(item.url),
            media_type=item.media_type.value,
            status=item.status.value,
            mime_type=item.metadata.mime_type,
            size_bytes=item.metadata.size_bytes,
            file_name=item.metadata.file_name,
            width=item.metadata.width,
            height=item.metadata.height,
            duration_seconds=item.metadata.duration_seconds,
            caption=item.caption,
            uploaded_by=str(item.uploaded_by),
            activity_id=str(item.activity_id) if item.activity_id else None,
            expense_id=str(item.expense_id) if item.expense_id else None,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )


@dataclass(frozen=True)
class MediaCollectionSummary:
    """Summary DTO for a TripMediaCollection aggregate."""

    collection_id: str
    trip_id: str
    owner_id: str
    media_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_aggregate(cls, collection: TripMediaCollection) -> MediaCollectionSummary:
        return cls(
            collection_id=str(collection.collection_id),
            trip_id=str(collection.trip_id),
            owner_id=str(collection.owner_id),
            media_count=len([item for item in collection.items if item.status.value != "deleted"]),
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )


@dataclass(frozen=True)
class MediaListPage:
    """Cursor-paginated page of media items."""

    items: tuple[MediaItemSummary, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


# Result type aliases (Python 3.11 compatible TypeAlias with noqa UP040)
UploadMediaResult: TypeAlias = "Result[MediaItemSummary]"  # noqa: UP040
UpdateCaptionResult: TypeAlias = "Result[MediaItemSummary]"  # noqa: UP040
DeleteMediaResult: TypeAlias = "Result[None]"  # noqa: UP040
AttachMediaToActivityResult: TypeAlias = "Result[MediaItemSummary]"  # noqa: UP040
AttachMediaToExpenseResult: TypeAlias = "Result[MediaItemSummary]"  # noqa: UP040
GetMediaResult: TypeAlias = "Result[MediaItemSummary]"  # noqa: UP040
ListMediaResult: TypeAlias = "Result[MediaListPage]"  # noqa: UP040
GetMediaByActivityResult: TypeAlias = "Result[list[MediaItemSummary]]"  # noqa: UP040
GetMediaByExpenseResult: TypeAlias = "Result[list[MediaItemSummary]]"  # noqa: UP040
