"""CollaborationId value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class CollaborationId(ValueObject):
    """Unique identifier for a TripCollaboration aggregate."""

    value: UUID

    @classmethod
    def generate(cls) -> CollaborationId:
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> CollaborationId:
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
