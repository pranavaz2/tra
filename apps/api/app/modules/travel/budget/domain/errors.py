"""Domain and application errors for the Budget bounded context."""

from __future__ import annotations

from uuid import UUID

from app.shared.domain.errors import ConflictError, DomainError, NotFoundError


class BudgetNotFoundError(NotFoundError):
    """The requested TripBudget does not exist."""

    code = "budget_not_found"

    def __init__(self, id_or_trip: UUID | str) -> None:
        super().__init__("budget", id_or_trip)


class BudgetAlreadyExistsError(ConflictError):
    """The trip already has a budget."""

    code = "budget_already_exists"

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip '{trip_id}' already has a budget.")


class ExpenseNotFoundError(NotFoundError):
    """The requested Expense does not exist."""

    code = "expense_not_found"

    def __init__(self, expense_id: UUID | str) -> None:
        super().__init__("expense", expense_id)


class CategoryNotFoundError(NotFoundError):
    """The requested BudgetCategory does not exist."""

    code = "category_not_found"

    def __init__(self, category_id: UUID | str) -> None:
        super().__init__("category", category_id)


class DuplicateCategoryNameError(ConflictError):
    """A category with the given name already exists in this budget."""

    code = "duplicate_category_name"

    def __init__(self, name: str) -> None:
        super().__init__(f"Category with name '{name}' already exists.")


class BudgetAlreadyClosedError(DomainError):
    """Mutations are disallowed on a closed budget."""

    code = "budget_already_closed"

    def __init__(self) -> None:
        super().__init__("This budget is closed and cannot be modified.")


class CurrencyMismatchError(DomainError):
    """Expense currency does not match budget currency."""

    code = "currency_mismatch"

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            f"Currency mismatch. Expected budget currency '{expected}', but got '{actual}'."
        )


class TotalSpentCannotBeNegativeError(DomainError):
    """The total spent amount cannot be negative."""

    code = "total_spent_cannot_be_negative"

    def __init__(self) -> None:
        super().__init__("The total spent amount cannot become negative.")


class BudgetLimitMustBePositiveError(DomainError):
    """The budget limit amount must be positive."""

    code = "budget_limit_must_be_positive"

    def __init__(self) -> None:
        super().__init__("Budget limit total must be greater than zero.")
