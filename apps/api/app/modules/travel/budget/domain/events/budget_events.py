"""Budget domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class BudgetCreated(DomainEvent):
    """Emitted when a new TripBudget aggregate is created."""

    budget_id: str
    trip_id: str
    limit_amount: str
    currency: str
    status: str


@dataclass(frozen=True, kw_only=True)
class BudgetUpdated(DomainEvent):
    """Emitted when TripBudget properties (limit, status) are updated."""

    budget_id: str
    trip_id: str
    limit_amount: str
    currency: str
    status: str


@dataclass(frozen=True, kw_only=True)
class ExpenseAdded(DomainEvent):
    """Emitted when an expense is added to the budget."""

    budget_id: str
    expense_id: str
    title: str
    amount: str
    category_id: str
    expense_type: str
    expense_date: date


@dataclass(frozen=True, kw_only=True)
class ExpenseUpdated(DomainEvent):
    """Emitted when an expense is updated."""

    budget_id: str
    expense_id: str
    title: str
    amount: str
    category_id: str
    expense_type: str
    expense_date: date


@dataclass(frozen=True, kw_only=True)
class ExpenseDeleted(DomainEvent):
    """Emitted when an expense is removed from the budget."""

    budget_id: str
    expense_id: str


@dataclass(frozen=True, kw_only=True)
class BudgetThresholdExceeded(DomainEvent):
    """Emitted when the spent amount crosses a threshold percentage."""

    budget_id: str
    trip_id: str
    threshold_percentage: int
    total_spent: str
    budget_limit: str
    currency: str
