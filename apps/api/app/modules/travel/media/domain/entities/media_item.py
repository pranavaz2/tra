"""MediaItem entity representing a single file attachment."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.media.domain.enums.media_status import MediaStatus
from app.modules.travel.media.domain.enums.media_type import MediaType
from app.modules.travel.media.domain.errors import CaptionLengthExceededError
from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl
from app.shared.domain.entity import Entity

_MAX_CAPTION_LENGTH = 500


@dataclass(kw_only=True, eq=False)
class MediaItem(Entity[MediaId]):
    """
    MediaItem entity.

    Represents a photo, video, note, voice memo, or receipt uploaded
    by a user and linked to a trip.
    """

    collection_id: MediaCollectionId
    url: MediaUrl
    media_type: MediaType
    status: MediaStatus
    metadata: MediaMetadata
    caption: str | None = None
    uploaded_by: UserId
    activity_id: ActivityId | None = None
    expense_id: ExpenseId | None = None

    def __post_init__(self) -> None:
        if self.caption is not None:
            stripped = self.caption.strip()
            if len(stripped) > _MAX_CAPTION_LENGTH:
                raise CaptionLengthExceededError(len(stripped), _MAX_CAPTION_LENGTH)
            object.__setattr__(self, "caption", stripped if stripped else None)

    def update_caption(self, caption: str | None) -> None:
        """Update the caption with length validation."""
        if caption is not None:
            stripped = caption.strip()
            if len(stripped) > _MAX_CAPTION_LENGTH:
                raise CaptionLengthExceededError(len(stripped), _MAX_CAPTION_LENGTH)
            caption = stripped if stripped else None
        else:
            caption = None

        self.caption = caption
        self.touch()

    def update_status(self, status: MediaStatus) -> None:
        """Update status of the item."""
        self.status = status
        self.touch()

    def attach_activity(self, activity_id: ActivityId) -> None:
        """Link this media to an activity."""
        self.activity_id = activity_id
        self.touch()

    def attach_expense(self, expense_id: ExpenseId) -> None:
        """Link this media to an expense."""
        self.expense_id = expense_id
        self.touch()
