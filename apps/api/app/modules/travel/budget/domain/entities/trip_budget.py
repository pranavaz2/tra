"""TripBudget aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.entities.budget_category import BudgetCategory
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.enums.budget_status import BudgetStatus
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.errors import (
    BudgetAlreadyClosedError,
    BudgetLimitMustBePositiveError,
    CategoryNotFoundError,
    CurrencyMismatchError,
    DuplicateCategoryNameError,
    ExpenseNotFoundError,
)
from app.modules.travel.budget.domain.events.budget_events import (
    BudgetCreated,
    BudgetThresholdExceeded,
    BudgetUpdated,
    ExpenseAdded,
    ExpenseDeleted,
    ExpenseUpdated,
)
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot


@dataclass(kw_only=True, eq=False)
class TripBudget(AggregateRoot[BudgetId]):
    """
    TripBudget aggregate root.

    Manages a trip's total budget limit, budget categories, and detailed expenses.
    Enforces monetary invariants, currency consistency, category uniqueness,
    and handles budget threshold alerts (50%, 75%, 90%, 100%).
    """

    trip_id: TripId
    owner_id: UserId
    limit: Money
    status: BudgetStatus = BudgetStatus.ACTIVE
    categories: list[BudgetCategory] = field(default_factory=list)
    expenses: list[Expense] = field(default_factory=list)
    exceeded_thresholds: set[int] = field(default_factory=set)
    version: int = 1
    deleted_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        budget_id: BudgetId,
        trip_id: TripId,
        owner_id: UserId,
        limit: Money,
    ) -> TripBudget:
        """Create a new TripBudget aggregate with standard categories."""
        if not limit.is_positive():
            raise BudgetLimitMustBePositiveError()

        budget = cls(
            entity_id=budget_id,
            trip_id=trip_id,
            owner_id=owner_id,
            limit=limit,
            status=BudgetStatus.ACTIVE,
            version=1,
        )

        # Pre-populate default categories
        default_categories = [
            ("Activity", "Sightseeing and tours"),
            ("Transport", "Flights, trains, and local transit"),
            ("Lodging", "Hotels, hostels, and Airbnb"),
            ("Food & Dining", "Restaurants, bars, and groceries"),
            ("Other", "Miscellaneous expenses"),
        ]
        for name, desc in default_categories:
            budget.categories.append(
                BudgetCategory(
                    entity_id=CategoryId.generate(),
                    name=name,
                    description=desc,
                )
            )

        budget.push_event(
            BudgetCreated(
                aggregate_id=str(budget_id),
                budget_id=str(budget_id),
                trip_id=str(trip_id),
                limit_amount=str(limit.amount),
                currency=str(limit.currency),
                status=budget.status.value,
            )
        )

        return budget

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                  #
    # ------------------------------------------------------------------ #

    @property
    def budget_id(self) -> BudgetId:
        """Alias for entity_id with the concrete BudgetId type."""
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                      #
    # ------------------------------------------------------------------ #

    @property
    def is_deleted(self) -> bool:
        """True if this budget has been soft-deleted."""
        return self.deleted_at is not None

    @property
    def total_spent(self) -> Money:
        """Calculate total spent from active expenses."""
        amount = sum(e.amount.amount for e in self.expenses)
        return Money(amount=amount, currency=self.limit.currency)

    @property
    def remaining_budget(self) -> Money:
        """Calculate remaining budget allowance."""
        return self.limit.subtract(self.total_spent)

    @property
    def spent_percentage(self) -> Decimal:
        """Spent percentage of the budget limit."""
        if self.limit.amount == Decimal("0.00"):
            return Decimal("0.00")
        percentage = (self.total_spent.amount / self.limit.amount) * 100
        return percentage.quantize(Decimal("0.01"))

    # ------------------------------------------------------------------ #
    # Private helpers                                                    #
    # ------------------------------------------------------------------ #

    def _guard_active(self) -> None:
        if self.is_deleted:
            raise BudgetAlreadyClosedError()
        if self.status == BudgetStatus.CLOSED:
            raise BudgetAlreadyClosedError()

    def _mutate(self) -> None:
        """Increment version and touch audit timestamp."""
        self.version += 1
        self.touch()

    def _check_thresholds(self) -> None:
        """Check and raise threshold events when spend limit is crossed."""
        percentage = self.spent_percentage
        limit_amount = self.limit.amount
        total_spent_amount = self.total_spent.amount

        for threshold in (50, 75, 90, 100):
            if percentage >= threshold:
                if threshold not in self.exceeded_thresholds:
                    self.exceeded_thresholds.add(threshold)
                    self.push_event(
                        BudgetThresholdExceeded(
                            aggregate_id=str(self.budget_id),
                            budget_id=str(self.budget_id),
                            trip_id=str(self.trip_id),
                            threshold_percentage=threshold,
                            total_spent=str(total_spent_amount),
                            budget_limit=str(limit_amount),
                            currency=str(self.limit.currency),
                        )
                    )
            else:
                if threshold in self.exceeded_thresholds:
                    self.exceeded_thresholds.remove(threshold)

    # ------------------------------------------------------------------ #
    # Mutations                                                          #
    # ------------------------------------------------------------------ #

    def update_limit(self, new_limit: Money) -> None:
        """Update the budget total limit."""
        self._guard_active()
        if not new_limit.is_positive():
            raise BudgetLimitMustBePositiveError()
        if new_limit.currency != self.limit.currency:
            raise CurrencyMismatchError(
                str(self.limit.currency), str(new_limit.currency)
            )

        self.limit = new_limit
        self._check_thresholds()
        self._mutate()

        self.push_event(
            BudgetUpdated(
                aggregate_id=str(self.budget_id),
                budget_id=str(self.budget_id),
                trip_id=str(self.trip_id),
                limit_amount=str(self.limit.amount),
                currency=str(self.limit.currency),
                status=self.status.value,
            )
        )

    def close(self) -> None:
        """Close the budget to disallow further modifications."""
        self._guard_active()
        self.status = BudgetStatus.CLOSED
        self._mutate()

        self.push_event(
            BudgetUpdated(
                aggregate_id=str(self.budget_id),
                budget_id=str(self.budget_id),
                trip_id=str(self.trip_id),
                limit_amount=str(self.limit.amount),
                currency=str(self.limit.currency),
                status=self.status.value,
            )
        )

    def reopen(self) -> None:
        """Reopen a closed budget."""
        if self.is_deleted:
            raise BudgetAlreadyClosedError()
        self.status = BudgetStatus.ACTIVE
        self._mutate()

        self.push_event(
            BudgetUpdated(
                aggregate_id=str(self.budget_id),
                budget_id=str(self.budget_id),
                trip_id=str(self.trip_id),
                limit_amount=str(self.limit.amount),
                currency=str(self.limit.currency),
                status=self.status.value,
            )
        )

    def add_category(self, category: BudgetCategory) -> None:
        """Add a custom category to the budget."""
        self._guard_active()
        normalized_name = category.name.lower()
        if any(c.name.lower() == normalized_name for c in self.categories):
            raise DuplicateCategoryNameError(category.name)

        self.categories.append(category)
        self._mutate()

    def add_expense(self, expense: Expense) -> None:
        """Add an expense to the budget."""
        self._guard_active()
        if expense.amount.currency != self.limit.currency:
            raise CurrencyMismatchError(
                str(self.limit.currency), str(expense.amount.currency)
            )

        # Verify category exists
        if not any(c.entity_id == expense.category_id for c in self.categories):
            raise CategoryNotFoundError(str(expense.category_id))

        self.expenses.append(expense)
        self._check_thresholds()
        self._mutate()

        self.push_event(
            ExpenseAdded(
                aggregate_id=str(self.budget_id),
                budget_id=str(self.budget_id),
                expense_id=str(expense.entity_id),
                title=expense.title,
                amount=str(expense.amount.amount),
                category_id=str(expense.category_id),
                expense_type=expense.expense_type.value,
                expense_date=expense.expense_date,
            )
        )

    def update_expense(
        self,
        expense_id: ExpenseId,
        *,
        title: str | None = None,
        amount: Money | None = None,
        category_id: CategoryId | None = None,
        expense_type: ExpenseType | None = None,
        description: str | None = None,
        expense_date: date | None = None,
    ) -> None:
        """Update an existing expense's properties."""
        self._guard_active()
        expense = next((e for e in self.expenses if e.entity_id == expense_id), None)
        if expense is None:
            raise ExpenseNotFoundError(str(expense_id))

        if amount is not None:
            if amount.currency != self.limit.currency:
                raise CurrencyMismatchError(
                    str(self.limit.currency), str(amount.currency)
                )
            expense.amount = amount

        if category_id is not None:
            if not any(c.entity_id == category_id for c in self.categories):
                raise CategoryNotFoundError(str(category_id))
            expense.category_id = category_id

        if title is not None:
            expense.title = title
        if expense_type is not None:
            expense.expense_type = expense_type
        if description is not None:
            expense.description = description
        if expense_date is not None:
            expense.expense_date = expense_date

        expense.touch()
        self._check_thresholds()
        self._mutate()

        self.push_event(
            ExpenseUpdated(
                aggregate_id=str(self.budget_id),
                budget_id=str(self.budget_id),
                expense_id=str(expense_id),
                title=expense.title,
                amount=str(expense.amount.amount),
                category_id=str(expense.category_id),
                expense_type=expense.expense_type.value,
                expense_date=expense.expense_date,
            )
        )

    def delete_expense(self, expense_id: ExpenseId) -> None:
        """Delete an expense from the budget."""
        self._guard_active()
        expense = next((e for e in self.expenses if e.entity_id == expense_id), None)
        if expense is None:
            raise ExpenseNotFoundError(str(expense_id))

        self.expenses.remove(expense)
        self._check_thresholds()
        self._mutate()

        self.push_event(
            ExpenseDeleted(
                aggregate_id=str(self.budget_id),
                budget_id=str(self.budget_id),
                expense_id=str(expense_id),
            )
        )

    def delete(self) -> None:
        """Soft-delete the budget aggregate."""
        if self.is_deleted:
            raise BudgetAlreadyClosedError()
        self.deleted_at = datetime.now(UTC)
        self._mutate()
