"""MediaType enum."""

from enum import StrEnum


class MediaType(StrEnum):
    """Supported types of media items."""

    PHOTO = "photo"
    VIDEO = "video"
    NOTE = "note"
    VOICE_MEMO = "voice_memo"
    RECEIPT = "receipt"
