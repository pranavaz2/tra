"""Media domain events."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class MediaUploaded(DomainEvent):
    """Emitted when a new media item is uploaded and added to a trip's collection."""

    media_collection_id: str
    trip_id: str
    media_id: str
    url: str
    media_type: str
    uploaded_by: str


@dataclass(frozen=True, kw_only=True)
class MediaDeleted(DomainEvent):
    """Emitted when a media item is soft-deleted."""

    media_collection_id: str
    media_id: str


@dataclass(frozen=True, kw_only=True)
class MediaCaptionUpdated(DomainEvent):
    """Emitted when the caption of a media item is updated."""

    media_collection_id: str
    media_id: str
    caption: str | None


@dataclass(frozen=True, kw_only=True)
class MediaAttachedToActivity(DomainEvent):
    """Emitted when a media item is attached to an activity."""

    media_collection_id: str
    media_id: str
    activity_id: str


@dataclass(frozen=True, kw_only=True)
class MediaAttachedToExpense(DomainEvent):
    """Emitted when a media item is attached to an expense."""

    media_collection_id: str
    media_id: str
    expense_id: str
