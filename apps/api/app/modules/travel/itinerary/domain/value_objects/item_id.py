"""ItemId — unique identity for the ItineraryItem entity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ItineraryItemId(ValueObject):
    """Wraps a UUID as the ItineraryItem's primary identity."""

    value: UUID

    @classmethod
    def generate(cls) -> ItineraryItemId:
        """Create a new random ItineraryItemId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> ItineraryItemId:
        """Parse a UUID string. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
