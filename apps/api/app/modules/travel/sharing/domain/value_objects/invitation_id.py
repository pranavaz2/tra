"""InvitationId value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class InvitationId(ValueObject):
    """Unique identifier for an Invitation entity."""

    value: UUID

    @classmethod
    def generate(cls) -> InvitationId:
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> InvitationId:
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
