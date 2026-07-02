"""Session identity value object — wraps a UUID primary key."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class SessionId(ValueObject):
    """Unique identifier for an authentication session."""

    value: UUID

    @classmethod
    def generate(cls) -> "SessionId":
        """Create a new random SessionId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> "SessionId":
        """Parse a UUID string into a SessionId. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
