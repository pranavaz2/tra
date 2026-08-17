"""MediaMetadata value object containing file properties."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class MediaMetadata(ValueObject):
    """
    Immutable file metadata for a media item.

    Contains dimensions, file size, mime type, etc.
    """

    mime_type: str
    size_bytes: int
    file_name: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    additional_attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to a dictionary for persistence."""
        return {
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "file_name": self.file_name,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            **self.additional_attributes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MediaMetadata:
        """Create metadata object from a dictionary."""
        cleaned = dict(data)
        mime_type = cleaned.pop("mime_type", "application/octet-stream")
        size_bytes = int(cleaned.pop("size_bytes", 0))
        file_name = cleaned.pop("file_name", None)
        width = cleaned.pop("width", None)
        height = cleaned.pop("height", None)
        duration_seconds = cleaned.pop("duration_seconds", None)
        return cls(
            mime_type=mime_type,
            size_bytes=size_bytes,
            file_name=file_name,
            width=width,
            height=height,
            duration_seconds=duration_seconds,
            additional_attributes=cleaned,
        )
