"""Expense entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.shared.domain.entity import Entity
from app.shared.domain.errors import ValidationError


@dataclass(kw_only=True, eq=False)
class Expense(Entity[ExpenseId]):
    """
    Expense entity.

    Represents a specific financial spend within a TripBudget.
    """

    title: str
    amount: Money
    category_id: CategoryId
    expense_type: ExpenseType
    description: str | None = None
    expense_date: date

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValidationError("Expense title cannot be empty.", field="title")
        if not self.amount.is_positive():
            raise ValidationError(
                f"Expense amount must be positive. Got: {self.amount.amount}",
                field="amount",
                value=self.amount.amount,
            )
        object.__setattr__(self, "title", self.title.strip())
