"""BudgetTier enum."""

from __future__ import annotations

from enum import StrEnum


class BudgetTier(StrEnum):
    """Budget tiers for travel preferences."""

    BUDGET = "budget"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"

    @classmethod
    def from_str(cls, value: str) -> BudgetTier:
        """Create from a case-insensitive string, fallback to mid_range."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.MID_RANGE
