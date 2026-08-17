"""MemberId value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class MemberId(ValueObject):
    """Unique identifier for a TripMember entity."""

    value: UUID

    @classmethod
    def generate(cls) -> MemberId:
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> MemberId:
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
