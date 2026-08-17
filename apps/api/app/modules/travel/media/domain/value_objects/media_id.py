"""MediaId value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class MediaId(ValueObject):
    """Unique identifier for a MediaItem entity."""

    value: UUID

    @classmethod
    def generate(cls) -> MediaId:
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> MediaId:
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
