"""Unit tests for BudgetService using in-memory test doubles."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.unit_of_work import (
    InMemoryUnitOfWork,
)
from app.modules.travel.budget.application.budget_service import (
    BudgetService,
)
from app.modules.travel.budget.application.commands import (
    AddExpenseCommand,
    CreateBudgetCommand,
    UpdateExpenseCommand,
)
from app.modules.travel.budget.application.queries import (
    GetBudgetSummaryQuery,
)
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.events import BudgetThresholdExceeded
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.infrastructure.clock import FixedClock

# ------------------------------------------------------------------ #
# Test Constants                                                     #
# ------------------------------------------------------------------ #

FIXED_TIME = datetime(2026, 7, 14, 12, 0, 0, tzinfo=UTC)
FIXED_TRIP_UUID = UUID("b1836585-780c-40ef-8e8a-02d9a7442342")
FIXED_OWNER_UUID = UUID("da2c388a-2114-41d6-848e-6701bbabefd4")
FIXED_BUDGET_UUID = UUID("e819bcf8-87b4-4b55-8736-f3316dbcd3bf")

# ------------------------------------------------------------------ #
# Test Doubles                                                       #
# ------------------------------------------------------------------ #


class InMemoryBudgetRepository:
    """In-memory ITripBudgetRepository for unit testing."""

    def __init__(self) -> None:
        self._store: dict[UUID, TripBudget] = {}

    async def find_by_id(self, budget_id: BudgetId) -> TripBudget | None:
        return self._store.get(budget_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> TripBudget | None:
        # Find latest active budget for trip
        active_budgets = [
            b for b in self._store.values()
            if b.trip_id == trip_id and not b.is_deleted
        ]
        if not active_budgets:
            return None
        active_budgets.sort(key=lambda b: (b.created_at, b.budget_id.value), reverse=True)
        return active_budgets[0]

    async def save(self, budget: TripBudget) -> None:
        self._store[budget.budget_id.value] = budget

    async def delete(self, budget_id: BudgetId) -> None:
        self._store.pop(budget_id.value, None)

    async def exists(self, budget_id: BudgetId) -> bool:
        budget = self._store.get(budget_id.value)
        return budget is not None and not budget.is_deleted

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        return any(
            b.trip_id == trip_id and not b.is_deleted
            for b in self._store.values()
        )


class InMemoryTripRepository:
    """In-memory ITripRepository for unit testing."""

    def __init__(self) -> None:
        self._store: dict[UUID, Trip] = {}

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self._store.get(trip_id.value)

    async def save(self, trip: Trip) -> None:
        self._store[trip.trip_id.value] = trip

    async def exists(self, trip_id: TripId) -> bool:
        trip = self._store.get(trip_id.value)
        return trip is not None and not trip.is_deleted

    async def delete(self, trip_id: TripId) -> None:
        self._store.pop(trip_id.value, None)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: TripId | None = None,
        status_filter: Any = None,
    ) -> list[Trip]:
        return list(self._store.values())[:limit]

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        return list(self._store.values())

    async def exists_with_title(self, owner_id: UserId, title: TripTitle) -> bool:
        return False


class InMemoryEventPublisher:
    """In-memory EventPublisher for tracking events."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


class FixedUUIDProvider:
    """Deterministic UUID Provider."""

    def __init__(self, value: UUID) -> None:
        self._value = value

    def generate(self) -> UUID:
        return self._value


# ------------------------------------------------------------------ #
# Test Composers                                                     #
# ------------------------------------------------------------------ #


def _make_service(
    fixed_uuid: UUID = FIXED_BUDGET_UUID,
) -> tuple[
    BudgetService,
    InMemoryBudgetRepository,
    InMemoryTripRepository,
    InMemoryEventPublisher,
]:
    repo = InMemoryBudgetRepository()
    trip_repo = InMemoryTripRepository()
    uow = InMemoryUnitOfWork()
    pub = InMemoryEventPublisher()
    uuid_prov = FixedUUIDProvider(fixed_uuid)
    clock = FixedClock(FIXED_TIME)

    service = BudgetService(
        repository=repo,
        trip_repository=trip_repo,
        unit_of_work=uow,
        event_publisher=pub,
        uuid_provider=uuid_prov,
        clock=clock,
    )
    return service, repo, trip_repo, pub


# ------------------------------------------------------------------ #
# Unit Tests                                                         #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_create_budget_success() -> None:
    """Verify creating budget constructs and saves correctly."""
    service, repo, trip_repo, pub = _make_service()

    # Create and save a live trip
    trip_id = TripId(FIXED_TRIP_UUID)
    owner_id = UserId(FIXED_OWNER_UUID)
    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("My Hawaii Trip"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(
            departure_date=date.today(),
            return_date=date.today() + timedelta(days=5),
        ),
    )
    await trip_repo.save(trip)

    cmd = CreateBudgetCommand(
        trip_id=str(trip_id),
        limit_amount=Decimal("5000.00"),
        currency="USD",
        requester_id=str(owner_id),
    )

    result = await service.create_budget(cmd)
    assert isinstance(result, Success)
    summary = result.value
    assert summary.budget_id == str(FIXED_BUDGET_UUID)
    assert summary.limit == Decimal("5000.00")
    assert summary.currency == "USD"
    assert len(summary.categories) == 5

    # Check database persistence
    budget = await repo.find_by_id(BudgetId(FIXED_BUDGET_UUID))
    assert budget is not None
    assert budget.limit.amount == Decimal("5000.00")
    assert budget.trip_id == trip_id

    # Check published events
    assert len(pub.published) == 1
    assert pub.published[0].budget_id == str(FIXED_BUDGET_UUID)


@pytest.mark.asyncio
async def test_create_budget_forbidden() -> None:
    """Verify unauthorized requester cannot create a budget."""
    service, _, trip_repo, _ = _make_service()

    trip_id = TripId(FIXED_TRIP_UUID)
    owner_id = UserId(FIXED_OWNER_UUID)
    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("My Hawaii Trip"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(
            departure_date=date.today(),
            return_date=date.today() + timedelta(days=5),
        ),
    )
    await trip_repo.save(trip)

    cmd = CreateBudgetCommand(
        trip_id=str(trip_id),
        limit_amount=Decimal("5000.00"),
        currency="USD",
        requester_id=str(UserId.generate()),  # Unauthorized
    )

    result = await service.create_budget(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_add_expense_service_success() -> None:
    """Verify expense addition flow in application service."""
    service, repo, _trip_repo, _pub = _make_service()

    # Pre-populate budget
    trip_id = TripId(FIXED_TRIP_UUID)
    owner_id = UserId(FIXED_OWNER_UUID)
    budget = TripBudget.create(
        budget_id=BudgetId(FIXED_BUDGET_UUID),
        trip_id=trip_id,
        owner_id=owner_id,
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )
    await repo.save(budget)

    # Use first pre-populated category ID
    cat_id = str(budget.categories[0].entity_id)

    # Deterministic UUID for the new expense
    exp_uuid = UUID("828ef87a-5347-49d6-950c-e2f47fa183c5")
    service._uuid_provider = FixedUUIDProvider(exp_uuid)

    cmd = AddExpenseCommand(
        trip_id=str(trip_id),
        title="Bus to beach",
        amount=Decimal("35.00"),
        category_id=cat_id,
        expense_type="transport",
        expense_date=date.today(),
        description="Day 1 travel",
        requester_id=str(owner_id),
    )

    result = await service.add_expense(cmd)
    assert isinstance(result, Success)
    exp_summary = result.value
    assert exp_summary.expense_id == str(exp_uuid)
    assert exp_summary.amount == Decimal("35.00")
    assert exp_summary.category_id == cat_id
    assert exp_summary.expense_type == "transport"

    # Verify state in repo
    updated_budget = await repo.find_by_trip_id(trip_id)
    assert updated_budget is not None
    assert len(updated_budget.expenses) == 1
    assert updated_budget.total_spent.amount == Decimal("35.00")


@pytest.mark.asyncio
async def test_update_expense_service_success() -> None:
    """Verify updating expense updates repo state and triggers events."""
    service, repo, _, pub = _make_service()

    trip_id = TripId(FIXED_TRIP_UUID)
    owner_id = UserId(FIXED_OWNER_UUID)
    budget = TripBudget.create(
        budget_id=BudgetId(FIXED_BUDGET_UUID),
        trip_id=trip_id,
        owner_id=owner_id,
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )
    cat_id = budget.categories[0].entity_id
    exp_id = ExpenseId.generate()
    expense = Expense(
        entity_id=exp_id,
        title="Original hotel",
        amount=Money(amount=Decimal("500.00"), currency=CurrencyCode("USD")),
        category_id=cat_id,
        expense_type=ExpenseType.LODGING,
        expense_date=date.today(),
    )
    budget.add_expense(expense)
    await repo.save(budget)

    cmd = UpdateExpenseCommand(
        trip_id=str(trip_id),
        expense_id=str(exp_id),
        title="Updated luxury resort",
        amount=Decimal("750.00"),  # Triggering 75% threshold (750 / 1000 = 75%)
        category_id=None,
        expense_type=None,
        expense_date=None,
        description="Changed hotels",
        requester_id=str(owner_id),
    )

    result = await service.update_expense(cmd)
    assert isinstance(result, Success)
    assert result.value.title == "Updated luxury resort"
    assert result.value.amount == Decimal("750.00")

    events = pub.published
    assert any(
        isinstance(e, BudgetThresholdExceeded) and e.threshold_percentage == 75
        for e in events
    )


@pytest.mark.asyncio
async def test_get_budget_summary_breakdown() -> None:
    """Verify retrieving spent breakdowns grouped by category and type."""
    service, repo, _, _ = _make_service()

    trip_id = TripId(FIXED_TRIP_UUID)
    owner_id = UserId(FIXED_OWNER_UUID)
    budget = TripBudget.create(
        budget_id=BudgetId(FIXED_BUDGET_UUID),
        trip_id=trip_id,
        owner_id=owner_id,
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )

    cat_transport = budget.categories[1].entity_id  # Transport
    cat_dining = budget.categories[3].entity_id     # Food & Dining

    # Add transport expense
    budget.add_expense(
        Expense(
            entity_id=ExpenseId.generate(),
            title="Train tickets",
            amount=Money(amount=Decimal("100.00"), currency=CurrencyCode("USD")),
            category_id=cat_transport,
            expense_type=ExpenseType.TRANSPORT,
            expense_date=date.today(),
        )
    )

    # Add dining expense
    budget.add_expense(
        Expense(
            entity_id=ExpenseId.generate(),
            title="Fancy dinner",
            amount=Money(amount=Decimal("150.00"), currency=CurrencyCode("USD")),
            category_id=cat_dining,
            expense_type=ExpenseType.RESTAURANT,
            expense_date=date.today(),
        )
    )

    await repo.save(budget)

    query = GetBudgetSummaryQuery(trip_id=str(trip_id), requester_id=str(owner_id))
    result = await service.get_budget_summary(query)

    assert isinstance(result, Success)
    breakdown = result.value
    assert breakdown.budget.total_spent == Decimal("250.00")
    assert breakdown.category_breakdowns[str(cat_transport)] == Decimal("100.00")
    assert breakdown.category_breakdowns[str(cat_dining)] == Decimal("150.00")
    assert breakdown.type_breakdowns["transport"] == Decimal("100.00")
    assert breakdown.type_breakdowns["restaurant"] == Decimal("150.00")
