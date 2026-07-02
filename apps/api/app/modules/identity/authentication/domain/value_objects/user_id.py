"""User identity value object — wraps a UUID primary key."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class UserId(ValueObject):
    """Unique identifier for a user across the entire system."""

    value: UUID

    @classmethod
    def generate(cls) -> "UserId":
        """Create a new random UserId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> "UserId":
        """Parse a UUID string into a UserId. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
