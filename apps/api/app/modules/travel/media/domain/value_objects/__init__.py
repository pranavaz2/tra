"""Media domain value objects package."""

from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl

__all__ = [
    "ActivityId",
    "MediaCollectionId",
    "MediaId",
    "MediaMetadata",
    "MediaUrl",
]
