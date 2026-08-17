"""BudgetStatus enum."""

from enum import StrEnum


class BudgetStatus(StrEnum):
    """Status of the budget context."""

    ACTIVE = "active"
    CLOSED = "closed"
