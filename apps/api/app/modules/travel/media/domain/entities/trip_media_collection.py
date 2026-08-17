"""TripMediaCollection aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.media.domain.entities.media_item import MediaItem
from app.modules.travel.media.domain.enums.media_status import MediaStatus
from app.modules.travel.media.domain.enums.media_type import MediaType
from app.modules.travel.media.domain.errors import (
    DuplicateMediaIdError,
    MaxFileSizeExceededError,
    MediaCollectionAlreadyLockedError,
    MediaItemNotFoundError,
    MimeTypeNotSupportedError,
)
from app.modules.travel.media.domain.events.media_events import (
    MediaAttachedToActivity,
    MediaAttachedToExpense,
    MediaCaptionUpdated,
    MediaDeleted,
    MediaUploaded,
)
from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot

# Default maximum file size limit (e.g. 100MB)
DEFAULT_MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

SUPPORTED_MIME_TYPES = {
    # Images
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/heic",
    "image/heif",
    # Videos
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/webm",
    # Notes / Documents
    "text/plain",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Audio / Voice Memos
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/wav",
    "audio/webm",
    "audio/ogg",
}


@dataclass(kw_only=True, eq=False)
class TripMediaCollection(AggregateRoot[MediaCollectionId]):
    """
    TripMediaCollection aggregate root.

    Acts as a container for all media items associated with a single trip.
    """

    trip_id: TripId
    owner_id: UserId
    items: list[MediaItem] = field(default_factory=list)
    version: int = 1
    deleted_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        collection_id: MediaCollectionId,
        trip_id: TripId,
        owner_id: UserId,
    ) -> TripMediaCollection:
        """Create a new media collection container for a trip."""
        return cls(
            entity_id=collection_id,
            trip_id=trip_id,
            owner_id=owner_id,
            items=[],
            version=1,
        )

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                    #
    # ------------------------------------------------------------------ #

    @property
    def collection_id(self) -> MediaCollectionId:
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Guards                                                               #
    # ------------------------------------------------------------------ #

    def _guard_not_deleted(self) -> None:
        if self.deleted_at is not None:
            raise MediaCollectionAlreadyLockedError()

    def _mutate(self) -> None:
        self.version += 1
        self.touch()

    # ------------------------------------------------------------------ #
    # Methods / Mutations                                                  #
    # ------------------------------------------------------------------ #

    def upload_media(
        self,
        *,
        media_id: MediaId,
        url: MediaUrl,
        media_type: MediaType,
        metadata: MediaMetadata,
        uploaded_by: UserId,
        max_file_size: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    ) -> MediaItem:
        """
        Add a new media item to the collection.

        Enforces:
        - supported MIME types check.
        - maximum file size check.
        - unique media_id check.
        """
        self._guard_not_deleted()

        # Check for duplicates
        if any(item.entity_id == media_id for item in self.items):
            raise DuplicateMediaIdError(str(media_id))

        # Check file size limit
        if metadata.size_bytes > max_file_size:
            raise MaxFileSizeExceededError(metadata.size_bytes, max_file_size)

        # Check MIME type
        if metadata.mime_type.lower() not in SUPPORTED_MIME_TYPES:
            raise MimeTypeNotSupportedError(metadata.mime_type, sorted(SUPPORTED_MIME_TYPES))

        media_item = MediaItem(
            entity_id=media_id,
            collection_id=self.collection_id,
            url=url,
            media_type=media_type,
            status=MediaStatus.AVAILABLE,
            metadata=metadata,
            uploaded_by=uploaded_by,
        )

        self.items.append(media_item)
        self._mutate()

        self.push_event(
            MediaUploaded(
                aggregate_id=str(self.collection_id),
                media_collection_id=str(self.collection_id),
                trip_id=str(self.trip_id),
                media_id=str(media_id),
                url=str(url),
                media_type=media_type.value,
                uploaded_by=str(uploaded_by),
            )
        )

        return media_item

    def update_caption(self, media_id: MediaId, caption: str | None) -> None:
        """Update caption of a media item."""
        self._guard_not_deleted()

        item = self._find_item(media_id)
        if item is None or item.status == MediaStatus.DELETED:
            raise MediaItemNotFoundError(str(media_id))

        item.update_caption(caption)
        self._mutate()

        self.push_event(
            MediaCaptionUpdated(
                aggregate_id=str(self.collection_id),
                media_collection_id=str(self.collection_id),
                media_id=str(media_id),
                caption=item.caption,
            )
        )

    def delete_media(self, media_id: MediaId) -> None:
        """Soft delete a media item."""
        self._guard_not_deleted()

        item = self._find_item(media_id)
        if item is None or item.status == MediaStatus.DELETED:
            raise MediaItemNotFoundError(str(media_id))

        item.update_status(MediaStatus.DELETED)
        self._mutate()

        self.push_event(
            MediaDeleted(
                aggregate_id=str(self.collection_id),
                media_collection_id=str(self.collection_id),
                media_id=str(media_id),
            )
        )

    def attach_to_activity(self, media_id: MediaId, activity_id: ActivityId) -> None:
        """Attach a media item to an activity."""
        self._guard_not_deleted()

        item = self._find_item(media_id)
        if item is None or item.status == MediaStatus.DELETED:
            raise MediaItemNotFoundError(str(media_id))

        item.attach_activity(activity_id)
        self._mutate()

        self.push_event(
            MediaAttachedToActivity(
                aggregate_id=str(self.collection_id),
                media_collection_id=str(self.collection_id),
                media_id=str(media_id),
                activity_id=str(activity_id),
            )
        )

    def attach_to_expense(self, media_id: MediaId, expense_id: ExpenseId) -> None:
        """Attach a media item to an expense."""
        self._guard_not_deleted()

        item = self._find_item(media_id)
        if item is None or item.status == MediaStatus.DELETED:
            raise MediaItemNotFoundError(str(media_id))

        item.attach_expense(expense_id)
        self._mutate()

        self.push_event(
            MediaAttachedToExpense(
                aggregate_id=str(self.collection_id),
                media_collection_id=str(self.collection_id),
                media_id=str(media_id),
                expense_id=str(expense_id),
            )
        )

    def delete(self) -> None:
        """Soft delete the aggregate root itself."""
        self._guard_not_deleted()
        self.deleted_at = datetime.now(UTC)
        self._mutate()

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _find_item(self, media_id: MediaId) -> MediaItem | None:
        return next((item for item in self.items if item.entity_id == media_id), None)
