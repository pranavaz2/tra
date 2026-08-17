"""Media domain events package."""

from app.modules.travel.media.domain.events.media_events import (
    MediaAttachedToActivity,
    MediaAttachedToExpense,
    MediaCaptionUpdated,
    MediaDeleted,
    MediaUploaded,
)

__all__ = [
    "MediaAttachedToActivity",
    "MediaAttachedToExpense",
    "MediaCaptionUpdated",
    "MediaDeleted",
    "MediaUploaded",
]
