"""Media domain entities package."""

from app.modules.travel.media.domain.entities.media_item import MediaItem
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)

__all__ = ["MediaItem", "TripMediaCollection"]
