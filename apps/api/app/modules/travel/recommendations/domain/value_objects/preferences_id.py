"""PreferencesId value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class PreferencesId(ValueObject):
    """Unique identifier for a UserPreferences aggregate."""

    value: UUID

    @classmethod
    def generate(cls) -> PreferencesId:
        """Generate a random PreferencesId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> PreferencesId:
        """Create a PreferencesId from a string representation."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
