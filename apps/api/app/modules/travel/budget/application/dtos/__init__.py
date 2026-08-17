"""Budget application DTOs and result type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TypeAlias

from app.modules.travel.budget.domain.entities.budget_category import BudgetCategory
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.shared.domain.result import Result


@dataclass(frozen=True)
class CategorySummary:
    """Summary DTO for a BudgetCategory."""

    category_id: str
    name: str
    description: str | None
    icon: str | None

    @classmethod
    def from_entity(cls, category: BudgetCategory) -> CategorySummary:
        return cls(
            category_id=str(category.entity_id),
            name=category.name,
            description=category.description,
            icon=category.icon,
        )


@dataclass(frozen=True)
class ExpenseSummary:
    """Summary DTO for an Expense."""

    expense_id: str
    title: str
    amount: Decimal
    currency: str
    category_id: str
    expense_type: str
    expense_date: date
    description: str | None
    created_at: datetime

    @classmethod
    def from_entity(cls, expense: Expense) -> ExpenseSummary:
        return cls(
            expense_id=str(expense.entity_id),
            title=expense.title,
            amount=expense.amount.amount,
            currency=str(expense.amount.currency),
            category_id=str(expense.category_id),
            expense_type=expense.expense_type.value,
            expense_date=expense.expense_date,
            description=expense.description,
            created_at=expense.created_at,
        )


@dataclass(frozen=True)
class BudgetSummary:
    """Summary DTO for a TripBudget."""

    budget_id: str
    trip_id: str
    owner_id: str
    limit: Decimal
    currency: str
    status: str
    total_spent: Decimal
    remaining: Decimal
    spent_percentage: Decimal
    categories: list[CategorySummary]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_aggregate(cls, budget: TripBudget) -> BudgetSummary:
        return cls(
            budget_id=str(budget.budget_id),
            trip_id=str(budget.trip_id),
            owner_id=str(budget.owner_id),
            limit=budget.limit.amount,
            currency=str(budget.limit.currency),
            status=budget.status.value,
            total_spent=budget.total_spent.amount,
            remaining=budget.remaining_budget.amount,
            spent_percentage=budget.spent_percentage,
            categories=[CategorySummary.from_entity(c) for c in budget.categories],
            created_at=budget.created_at,
            updated_at=budget.updated_at,
        )


@dataclass(frozen=True)
class ExpenseListPage:
    """Opaque cursor-paginated page of expenses."""

    items: tuple[ExpenseSummary, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


@dataclass(frozen=True)
class BudgetBreakdownSummary:
    """Complete budget summary with spending breakdown."""

    budget: BudgetSummary
    category_breakdowns: dict[str, Decimal]  # Category ID -> spent amount
    type_breakdowns: dict[str, Decimal]      # Expense type -> spent amount


# Result type aliases (using Python 3.11 compatible TypeAlias with noqa UP040)
CreateBudgetResult: TypeAlias = "Result[BudgetSummary]"  # noqa: UP040
UpdateBudgetResult: TypeAlias = "Result[BudgetSummary]"  # noqa: UP040
AddExpenseResult: TypeAlias = "Result[ExpenseSummary]"  # noqa: UP040
UpdateExpenseResult: TypeAlias = "Result[ExpenseSummary]"  # noqa: UP040
DeleteExpenseResult: TypeAlias = "Result[None]"  # noqa: UP040
GetBudgetResult: TypeAlias = "Result[BudgetSummary]"  # noqa: UP040
ListExpensesResult: TypeAlias = "Result[ExpenseListPage]"  # noqa: UP040
GetBudgetSummaryResult: TypeAlias = "Result[BudgetBreakdownSummary]"  # noqa: UP040
