"""ITripBudgetRepository Protocol interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


@runtime_checkable
class ITripBudgetRepository(Protocol):
    """Persistence interface for TripBudget aggregates."""

    async def find_by_id(self, budget_id: BudgetId) -> TripBudget | None:
        """Find budget by ID. Soft-deleted ones are returned."""
        ...

    async def find_by_trip_id(self, trip_id: TripId) -> TripBudget | None:
        """Find the latest active (non-deleted) budget for a trip."""
        ...

    async def save(self, budget: TripBudget) -> None:
        """Persist/update budget aggregate."""
        ...

    async def delete(self, budget_id: BudgetId) -> None:
        """Hard-delete a budget row."""
        ...

    async def exists(self, budget_id: BudgetId) -> bool:
        """Check if budget exists and is not soft-deleted."""
        ...

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Check if a non-deleted budget exists for the trip."""
        ...
