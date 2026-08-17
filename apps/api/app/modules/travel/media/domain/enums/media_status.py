"""MediaStatus enum."""

from enum import StrEnum


class MediaStatus(StrEnum):
    """Upload and processing status of a media item."""

    UPLOADING = "uploading"
    AVAILABLE = "available"
    FAILED = "failed"
    DELETED = "deleted"
