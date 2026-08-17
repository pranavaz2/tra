"""Budget application commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CreateBudgetCommand:
    """Command to create a budget for a trip."""

    trip_id: str
    limit_amount: Decimal
    currency: str
    requester_id: str


@dataclass(frozen=True)
class UpdateBudgetCommand:
    """Command to update budget limit or status."""

    trip_id: str
    limit_amount: Decimal | None
    status: str | None
    requester_id: str


@dataclass(frozen=True)
class AddExpenseCommand:
    """Command to add a new expense."""

    trip_id: str
    title: str
    amount: Decimal
    category_id: str
    expense_type: str
    expense_date: date
    description: str | None
    requester_id: str


@dataclass(frozen=True)
class UpdateExpenseCommand:
    """Command to update an existing expense."""

    trip_id: str
    expense_id: str
    title: str | None
    amount: Decimal | None
    category_id: str | None
    expense_type: str | None
    expense_date: date | None
    description: str | None
    requester_id: str


@dataclass(frozen=True)
class DeleteExpenseCommand:
    """Command to delete an expense."""

    trip_id: str
    expense_id: str
    requester_id: str
