"""DayId — unique identity for the ItineraryDay entity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ItineraryDayId(ValueObject):
    """Wraps a UUID as the ItineraryDay's primary identity."""

    value: UUID

    @classmethod
    def generate(cls) -> ItineraryDayId:
        """Create a new random ItineraryDayId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> ItineraryDayId:
        """Parse a UUID string. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
