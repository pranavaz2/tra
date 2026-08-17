"""ExpenseType enum."""

from enum import StrEnum


class ExpenseType(StrEnum):
    """Categorized type of an expense."""

    ACTIVITY = "activity"
    TRANSPORT = "transport"
    LODGING = "lodging"
    RESTAURANT = "restaurant"
    OTHER = "other"
