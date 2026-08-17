"""ActivityId value object representing an itinerary item ID."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ActivityId(ValueObject):
    """Unique identifier for an Activity (maps to ItineraryItemId)."""

    value: UUID

    @classmethod
    def generate(cls) -> ActivityId:
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> ActivityId:
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
