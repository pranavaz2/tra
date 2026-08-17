"""BudgetId value object."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class BudgetId(ValueObject):
    """Unique identifier for a TripBudget aggregate."""

    value: UUID

    @classmethod
    def generate(cls) -> BudgetId:
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> BudgetId:
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
