"""BudgetCategory entity."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.shared.domain.entity import Entity
from app.shared.domain.errors import ValidationError


@dataclass(kw_only=True, eq=False)
class BudgetCategory(Entity[CategoryId]):
    """
    BudgetCategory entity.

    Represents a classification for expenses (e.g. 'Food', 'Flights').
    """

    name: str
    description: str | None = None
    icon: str | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError("Category name cannot be empty.", field="name")
        object.__setattr__(self, "name", self.name.strip())
