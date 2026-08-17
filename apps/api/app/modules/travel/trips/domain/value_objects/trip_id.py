"""TripId — unique identity for the Trip aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class TripId(ValueObject):
    """Wraps a UUID as the Trip aggregate's primary identity."""

    value: UUID

    @classmethod
    def generate(cls) -> "TripId":
        """Create a new random TripId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> "TripId":
        """Parse a UUID string. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
