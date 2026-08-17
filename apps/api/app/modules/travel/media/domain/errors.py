"""Domain and application errors for the Media bounded context."""

from __future__ import annotations

from uuid import UUID

from app.shared.domain.errors import ConflictError, DomainError, NotFoundError


class MediaCollectionNotFoundError(NotFoundError):
    """The requested TripMediaCollection does not exist."""

    code = "media_collection_not_found"

    def __init__(self, id_or_trip: UUID | str) -> None:
        super().__init__("media collection", id_or_trip)


class MediaItemNotFoundError(NotFoundError):
    """The requested MediaItem does not exist within the collection."""

    code = "media_item_not_found"

    def __init__(self, media_id: UUID | str) -> None:
        super().__init__("media item", media_id)


class MediaCollectionAlreadyExistsError(ConflictError):
    """The trip already has a media collection."""

    code = "media_collection_already_exists"

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip '{trip_id}' already has a media collection.")


class DuplicateMediaIdError(DomainError):
    """A media item with the same ID already exists in this collection."""

    code = "duplicate_media_id"

    def __init__(self, media_id: str) -> None:
        super().__init__(f"Media item with ID '{media_id}' already exists in this collection.")


class MimeTypeNotSupportedError(DomainError):
    """The file's MIME type is not supported."""

    code = "mime_type_not_supported"

    def __init__(self, mime_type: str, supported: list[str]) -> None:
        super().__init__(
            f"MIME type '{mime_type}' is not supported. Supported types: {', '.join(supported)}"
        )


class MaxFileSizeExceededError(DomainError):
    """The file size exceeds the configured maximum limit."""

    code = "max_file_size_exceeded"

    def __init__(self, size: int, max_limit: int) -> None:
        super().__init__(f"File size {size} bytes exceeds the maximum limit of {max_limit} bytes.")


class CaptionLengthExceededError(DomainError):
    """Caption length exceeds the maximum limit."""

    code = "caption_length_exceeded"

    def __init__(self, length: int, max_limit: int) -> None:
        super().__init__(
            f"Caption length {length} exceeds the maximum allowed limit of {max_limit} characters."
        )


class MediaCollectionAlreadyLockedError(DomainError):
    """Mutations are disallowed on a deleted media collection."""

    code = "media_collection_already_locked"

    def __init__(self) -> None:
        super().__init__("This media collection is deleted and cannot be modified.")
