"""Unit tests for TripBudget aggregate root and entities."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.entities.budget_category import BudgetCategory
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.budget_status import BudgetStatus
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.errors import (
    BudgetAlreadyClosedError,
    BudgetLimitMustBePositiveError,
    CurrencyMismatchError,
    DuplicateCategoryNameError,
)
from app.modules.travel.budget.domain.events.budget_events import (
    BudgetCreated,
    BudgetThresholdExceeded,
    ExpenseAdded,
)
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


def test_budget_creation_success() -> None:
    """Test creating a TripBudget aggregate root."""
    b_id = BudgetId.generate()
    t_id = TripId.generate()
    o_id = UserId.generate()
    limit = Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD"))

    budget = TripBudget.create(
        budget_id=b_id,
        trip_id=t_id,
        owner_id=o_id,
        limit=limit,
    )

    assert budget.budget_id == b_id
    assert budget.trip_id == t_id
    assert budget.owner_id == o_id
    assert budget.limit == limit
    assert budget.status == BudgetStatus.ACTIVE
    assert len(budget.categories) == 5  # Pre-populated categories
    assert len(budget.expenses) == 0

    events = budget.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], BudgetCreated)
    assert events[0].limit_amount == "1000.00"
    assert events[0].currency == "USD"


def test_budget_creation_invalid_limit() -> None:
    """Test budget limit validation."""
    b_id = BudgetId.generate()
    t_id = TripId.generate()
    o_id = UserId.generate()
    limit = Money(amount=Decimal("0.00"), currency=CurrencyCode("USD"))

    with pytest.raises(BudgetLimitMustBePositiveError):
        TripBudget.create(
            budget_id=b_id,
            trip_id=t_id,
            owner_id=o_id,
            limit=limit,
        )


def test_budget_update_limit() -> None:
    """Test updating the limit amount and currency mismatch check."""
    budget = TripBudget.create(
        budget_id=BudgetId.generate(),
        trip_id=TripId.generate(),
        owner_id=UserId.generate(),
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )

    # Valid update
    budget.update_limit(Money(amount=Decimal("1500.00"), currency=CurrencyCode("USD")))
    assert budget.limit.amount == Decimal("1500.00")

    # Mismatched currency
    with pytest.raises(CurrencyMismatchError):
        budget.update_limit(Money(amount=Decimal("1500.00"), currency=CurrencyCode("EUR")))


def test_add_custom_category() -> None:
    """Test adding custom category and duplicate check."""
    budget = TripBudget.create(
        budget_id=BudgetId.generate(),
        trip_id=TripId.generate(),
        owner_id=UserId.generate(),
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )

    custom_cat = BudgetCategory(
        entity_id=CategoryId.generate(),
        name= "Medical insurance",
        description="Emergency insurance",
    )
    budget.add_category(custom_cat)
    assert custom_cat in budget.categories

    # Duplicate name check
    duplicate = BudgetCategory(
        entity_id=CategoryId.generate(),
        name="  medical INSURANCE  ",
    )
    with pytest.raises(DuplicateCategoryNameError):
        budget.add_category(duplicate)


def test_add_expense_flow() -> None:
    """Test adding an expense to the budget, currency check and event."""
    budget = TripBudget.create(
        budget_id=BudgetId.generate(),
        trip_id=TripId.generate(),
        owner_id=UserId.generate(),
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )

    cat_id = budget.categories[0].entity_id
    exp_id = ExpenseId.generate()
    expense = Expense(
        entity_id=exp_id,
        title="Bus tickets",
        amount=Money(amount=Decimal("50.00"), currency=CurrencyCode("USD")),
        category_id=cat_id,
        expense_type=ExpenseType.TRANSPORT,
        expense_date=date.today(),
    )

    budget.add_expense(expense)
    assert len(budget.expenses) == 1
    assert budget.total_spent.amount == Decimal("50.00")
    assert budget.remaining_budget.amount == Decimal("950.00")

    events = budget.pop_events()
    # 1 from budget creation might have been popped. Pop again to ensure only add event:
    assert any(isinstance(e, ExpenseAdded) for e in events)


def test_add_expense_mismatched_currency() -> None:
    """Verify currency constraint on expenses."""
    budget = TripBudget.create(
        budget_id=BudgetId.generate(),
        trip_id=TripId.generate(),
        owner_id=UserId.generate(),
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )

    cat_id = budget.categories[0].entity_id
    expense = Expense(
        entity_id=ExpenseId.generate(),
        title="Bus tickets",
        amount=Money(amount=Decimal("50.00"), currency=CurrencyCode("EUR")),
        category_id=cat_id,
        expense_type=ExpenseType.TRANSPORT,
        expense_date=date.today(),
    )

    with pytest.raises(CurrencyMismatchError):
        budget.add_expense(expense)


def test_closed_budget_rejection() -> None:
    """Disallow mutations on a closed budget."""
    budget = TripBudget.create(
        budget_id=BudgetId.generate(),
        trip_id=TripId.generate(),
        owner_id=UserId.generate(),
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )

    budget.close()
    assert budget.status == BudgetStatus.CLOSED

    # Disallow add expense
    cat_id = budget.categories[0].entity_id
    expense = Expense(
        entity_id=ExpenseId.generate(),
        title="Snacks",
        amount=Money(amount=Decimal("10.00"), currency=CurrencyCode("USD")),
        category_id=cat_id,
        expense_type=ExpenseType.RESTAURANT,
        expense_date=date.today(),
    )

    with pytest.raises(BudgetAlreadyClosedError):
        budget.add_expense(expense)

    with pytest.raises(BudgetAlreadyClosedError):
        budget.update_limit(Money(amount=Decimal("2000.00"), currency=CurrencyCode("USD")))


def test_threshold_alerts() -> None:
    """Verify threshold alert firing at 50%, 75%, 90%, 100%."""
    budget = TripBudget.create(
        budget_id=BudgetId.generate(),
        trip_id=TripId.generate(),
        owner_id=UserId.generate(),
        limit=Money(amount=Decimal("100.00"), currency=CurrencyCode("USD")),
    )
    budget.pop_events()  # Clear BudgetCreated event

    cat_id = budget.categories[0].entity_id

    # 1. Trigger 50%
    exp1 = Expense(
        entity_id=ExpenseId.generate(),
        title="Lunch",
        amount=Money(amount=Decimal("55.00"), currency=CurrencyCode("USD")),
        category_id=cat_id,
        expense_type=ExpenseType.RESTAURANT,
        expense_date=date.today(),
    )
    budget.add_expense(exp1)
    events = budget.pop_events()
    assert any(
        isinstance(e, BudgetThresholdExceeded) and e.threshold_percentage == 50
        for e in events
    )
    assert 50 in budget.exceeded_thresholds

    # 2. Trigger 75% and 90% in one go
    exp2 = Expense(
        entity_id=ExpenseId.generate(),
        title="Hotel",
        amount=Money(amount=Decimal("38.00"), currency=CurrencyCode("USD")),
        category_id=cat_id,
        expense_type=ExpenseType.LODGING,
        expense_date=date.today(),
    )
    budget.add_expense(exp2)
    # Total spent: 93 / 100 = 93% (crosses 75% and 90%)
    events = budget.pop_events()
    thresholds_fired = {
        e.threshold_percentage
        for e in events
        if isinstance(e, BudgetThresholdExceeded)
    }
    assert thresholds_fired == {75, 90}

    # 3. Trigger 100%
    exp3 = Expense(
        entity_id=ExpenseId.generate(),
        title="Drink",
        amount=Money(amount=Decimal("10.00"), currency=CurrencyCode("USD")),
        category_id=cat_id,
        expense_type=ExpenseType.RESTAURANT,
        expense_date=date.today(),
    )
    budget.add_expense(exp3)
    # Total spent: 103 / 100 = 103%
    events = budget.pop_events()
    assert any(
        isinstance(e, BudgetThresholdExceeded) and e.threshold_percentage == 100
        for e in events
    )

    # 4. Remove expense to drop below 100% and 90%
    budget.delete_expense(exp3.entity_id)
    budget.delete_expense(exp2.entity_id)
    # Total spent drops to 55 (only 50% threshold remains active)
    assert budget.exceeded_thresholds == {50}
