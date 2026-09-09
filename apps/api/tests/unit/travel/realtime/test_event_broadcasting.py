"""Unit tests for post-commit event broadcasting in ItineraryService and BudgetService."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.application.budget_service import BudgetService
from app.modules.travel.budget.application.commands import AddExpenseCommand, CreateBudgetCommand
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.itinerary.application.commands import AddItineraryDayCommand, CreateItineraryCommand
from app.modules.travel.itinerary.application.itinerary_service import ItineraryService
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.realtime.application.broadcaster import ITripEventBroadcaster
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.result import Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider
from app.shared.infrastructure.clock import FixedClock


class FakeUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, *args: any) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


class FakeEventPublisher(EventPublisher):
    def __init__(self) -> None:
        self.published_events: list = []

    async def publish(self, events: list) -> None:
        self.published_events.extend(events)


class FakeUUIDProvider(UUIDProvider):
    def __init__(self, uuids: list[uuid.UUID]) -> None:
        self.uuids = list(uuids)

    def generate(self) -> uuid.UUID:
        if not self.uuids:
            return uuid.uuid4()
        return self.uuids.pop(0)


@pytest.mark.asyncio
async def test_itinerary_service_broadcasts_on_add_day():
    """Verify ItineraryService broadcasts itinerary.day_created post-commit."""
    user_uuid = uuid.uuid4()
    trip_uuid = uuid.uuid4()
    itinerary_uuid = uuid.uuid4()

    owner_id = UserId(user_uuid)
    trip_id = TripId(trip_uuid)
    itinerary_id = ItineraryId(itinerary_uuid)

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Paris Tour"),
        privacy=TripPrivacy.PRIVATE,
    )

    itinerary = Itinerary.create(
        itinerary_id=itinerary_id,
        trip_id=trip_id,
    )

    mock_trip_repo = MagicMock()
    mock_trip_repo.find_by_id = AsyncMock(return_value=trip)

    mock_itinerary_repo = MagicMock()
    mock_itinerary_repo.find_by_id = AsyncMock(return_value=itinerary)
    mock_itinerary_repo.find_by_trip_id = AsyncMock(return_value=itinerary)
    mock_itinerary_repo.save = AsyncMock()

    mock_broadcaster = MagicMock(spec=ITripEventBroadcaster)
    mock_broadcaster.broadcast_to_trip = AsyncMock()

    uow = FakeUnitOfWork()
    publisher = FakeEventPublisher()
    uuid_provider = FakeUUIDProvider([uuid.uuid4(), uuid.uuid4()])

    service = ItineraryService(
        repository=mock_itinerary_repo,
        trip_repository=mock_trip_repo,
        unit_of_work=uow,
        event_publisher=publisher,
        uuid_provider=uuid_provider,
        event_broadcaster=mock_broadcaster,
    )

    command = AddItineraryDayCommand(
        trip_id=str(trip_uuid),
        requester_id=str(user_uuid),
        day_number=1,
        date=date(2026, 9, 10),
        title="Arrival Day",
    )

    result = await service.add_day(command)
    assert isinstance(result, Success)
    assert uow.committed
    mock_broadcaster.broadcast_to_trip.assert_awaited_once()

    args = mock_broadcaster.broadcast_to_trip.call_args[0]
    broadcasted_trip_id = args[0]
    broadcasted_event = args[1]
    assert broadcasted_trip_id == str(trip_uuid)
    assert broadcasted_event.trip_id == str(trip_uuid)
    assert broadcasted_event.event_type == "itinerary.day_created"
    assert broadcasted_event.actor_id == str(user_uuid)
    assert broadcasted_event.payload["day_number"] == 1


@pytest.mark.asyncio
async def test_budget_service_broadcasts_on_add_expense():
    """Verify BudgetService broadcasts budget.expense_created post-commit."""
    user_uuid = uuid.uuid4()
    trip_uuid = uuid.uuid4()
    budget_uuid = uuid.uuid4()

    owner_id = UserId(user_uuid)
    trip_id = TripId(trip_uuid)
    budget_id = BudgetId(budget_uuid)

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Tokyo Trip"),
        privacy=TripPrivacy.PRIVATE,
    )

    budget = TripBudget.create(
        budget_id=budget_id,
        trip_id=trip_id,
        owner_id=owner_id,
        limit=Money(Decimal("3000.00"), CurrencyCode("USD")),
    )
    category_id = budget.categories[0].entity_id.value

    mock_trip_repo = MagicMock()
    mock_trip_repo.find_by_id = AsyncMock(return_value=trip)

    mock_budget_repo = MagicMock()
    mock_budget_repo.find_by_id = AsyncMock(return_value=budget)
    mock_budget_repo.find_by_trip_id = AsyncMock(return_value=budget)
    mock_budget_repo.save = AsyncMock()

    mock_broadcaster = MagicMock(spec=ITripEventBroadcaster)
    mock_broadcaster.broadcast_to_trip = AsyncMock()

    uow = FakeUnitOfWork()
    publisher = FakeEventPublisher()
    uuid_provider = FakeUUIDProvider([uuid.uuid4(), uuid.uuid4()])
    clock = FixedClock(datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC))

    service = BudgetService(
        repository=mock_budget_repo,
        trip_repository=mock_trip_repo,
        unit_of_work=uow,
        event_publisher=publisher,
        uuid_provider=uuid_provider,
        clock=clock,
        event_broadcaster=mock_broadcaster,
    )

    command = AddExpenseCommand(
        trip_id=str(trip_uuid),
        title="Sushi Dinner",
        amount=Decimal("85.50"),
        category_id=str(category_id),
        expense_type="restaurant",
        expense_date=date(2026, 9, 12),
        description="Omakase dinner",
        requester_id=str(user_uuid),
    )

    result = await service.add_expense(command)
    assert isinstance(result, Success)
    assert uow.committed
    mock_broadcaster.broadcast_to_trip.assert_awaited_once()

    args = mock_broadcaster.broadcast_to_trip.call_args[0]
    broadcasted_trip_id = args[0]
    broadcasted_event = args[1]
    assert broadcasted_trip_id == str(trip_uuid)
    assert broadcasted_event.trip_id == str(trip_uuid)
    assert broadcasted_event.event_type == "budget.expense_created"
    assert broadcasted_event.actor_id == str(user_uuid)
    assert broadcasted_event.payload["title"] == "Sushi Dinner"
