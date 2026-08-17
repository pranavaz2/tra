"""MediaUrl value object enforcing HTTPS URLs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class MediaUrl(ValueObject):
    """
    Value object wrapping a media URL.

    Enforces that URLs must be valid and must use the HTTPS scheme.
    """

    value: str

    def __post_init__(self) -> None:
        try:
            parsed = urlparse(self.value)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL structure.")
            if parsed.scheme.lower() != "https":
                raise ValidationError("Only HTTPS URLs are supported.", field="url")
        except Exception as exc:
            if isinstance(exc, ValidationError):
                raise exc
            raise ValidationError(f"Invalid URL: {exc!s}", field="url") from exc

    def __str__(self) -> str:
        return self.value
