"""ItineraryId — unique identity for the Itinerary aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ItineraryId(ValueObject):
    """Wraps a UUID as the Itinerary aggregate's primary identity."""

    value: UUID

    @classmethod
    def generate(cls) -> ItineraryId:
        """Create a new random ItineraryId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> ItineraryId:
        """Parse a UUID string. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
