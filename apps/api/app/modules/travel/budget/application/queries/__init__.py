"""Budget application queries."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class GetBudgetQuery:
    """Query to get a trip budget by trip ID."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class ListExpensesQuery:
    """Query to list expenses for a trip budget with cursor-based pagination."""

    trip_id: str
    category_id: str | None
    requester_id: str
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(1, self.limit), MAX_PAGE_SIZE))


@dataclass(frozen=True)
class GetBudgetSummaryQuery:
    """Query to get a budget summary and spending breakdown by trip ID."""

    trip_id: str
    requester_id: str
