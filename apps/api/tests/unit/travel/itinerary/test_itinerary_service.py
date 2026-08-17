"""Unit tests for the Itinerary application service."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
import uuid
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.itinerary.application.commands import (
    CreateItineraryCommand,
    AddItineraryDayCommand,
    UpdateItineraryDayCommand,
    RemoveItineraryDayCommand,
    AddItineraryItemCommand,
    UpdateItineraryItemCommand,
    RemoveItineraryItemCommand,
)
from app.modules.travel.itinerary.application.queries import GetItineraryQuery
from app.modules.travel.itinerary.application.itinerary_service import ItineraryService
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.repositories.interfaces import IItineraryRepository
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider
from app.shared.domain.result import Failure, Success


# ─────────────────────────────────────────────────────────────────────────────
# Test Doubles
# ─────────────────────────────────────────────────────────────────────────────


class FakeTripRepository:
    def __init__(self) -> None:
        self.trips: dict[uuid.UUID, Trip] = {}

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self.trips.get(trip_id.value)

    async def save(self, trip: Trip) -> None:
        self.trips[trip.trip_id.value] = trip


class FakeItineraryRepository:
    def __init__(self) -> None:
        self.itineraries: dict[uuid.UUID, Itinerary] = {}

    async def find_by_id(self, itinerary_id: ItineraryId) -> Itinerary | None:
        return self.itineraries.get(itinerary_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        for it in self.itineraries.values():
            if it.trip_id == trip_id:
                return it
        return None

    async def save(self, itinerary: Itinerary) -> None:
        self.itineraries[itinerary.itinerary_id.value] = itinerary

    async def exists(self, itinerary_id: ItineraryId) -> bool:
        return itinerary_id.value in self.itineraries

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        for it in self.itineraries.values():
            if it.trip_id == trip_id and not it.is_deleted:
                return True
        return False


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
        self.published_events: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published_events.extend(events)


class FakeUUIDProvider(UUIDProvider):
    def __init__(self, uuids: list[uuid.UUID]) -> None:
        self.uuids = list(uuids)

    def generate(self) -> uuid.UUID:
        if not self.uuids:
            return uuid.uuid4()
        return self.uuids.pop(0)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def test_setup() -> dict[str, any]:
    trip_repo = FakeTripRepository()
    itinerary_repo = FakeItineraryRepository()
    uow = FakeUnitOfWork()
    publisher = FakeEventPublisher()
    
    generated_uuid = uuid.uuid4()
    uuid_provider = FakeUUIDProvider([generated_uuid])

    service = ItineraryService(
        repository=itinerary_repo,
        trip_repository=trip_repo,
        unit_of_work=uow,
        event_publisher=publisher,
        uuid_provider=uuid_provider,
    )

    # Create a stub trip
    owner_id = UserId.generate()
    trip_id = TripId.generate()
    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("France Tour"),
    )
    trip_repo.trips[trip_id.value] = trip

    return {
        "service": service,
        "trip_repo": trip_repo,
        "itinerary_repo": itinerary_repo,
        "uow": uow,
        "publisher": publisher,
        "trip": trip,
        "owner_id": owner_id,
        "generated_uuid": generated_uuid,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


def test_create_itinerary_success(test_setup: dict[str, any]) -> None:
    service = test_setup["service"]
    trip = test_setup["trip"]
    owner_id = test_setup["owner_id"]
    generated_uuid = test_setup["generated_uuid"]

    command = CreateItineraryCommand(
        trip_id=str(trip.trip_id),
        requester_id=str(owner_id),
    )

    async def run() -> None:
        result = await service.create_itinerary(command)
        assert isinstance(result, Success)
        assert result.value.itinerary_id == generated_uuid
        assert result.value.trip_id == trip.trip_id.value
        assert test_setup["uow"].committed is True
        assert len(test_setup["publisher"].published_events) == 1

    import anyio
    anyio.run(run)


def test_create_itinerary_forbidden(test_setup: dict[str, any]) -> None:
    service = test_setup["service"]
    trip = test_setup["trip"]
    other_user = UserId.generate()

    command = CreateItineraryCommand(
        trip_id=str(trip.trip_id),
        requester_id=str(other_user),
    )

    async def run() -> None:
        result = await service.create_itinerary(command)
        assert isinstance(result, Failure)

    import anyio
    anyio.run(run)


def test_get_itinerary_auto_creates_if_not_exists(test_setup: dict[str, any]) -> None:
    service = test_setup["service"]
    trip = test_setup["trip"]
    owner_id = test_setup["owner_id"]
    generated_uuid = test_setup["generated_uuid"]

    query = GetItineraryQuery(
        trip_id=str(trip.trip_id),
        requester_id=str(owner_id),
    )

    async def run() -> None:
        result = await service.get_itinerary(query)
        assert isinstance(result, Success)
        assert result.value.itinerary_id == generated_uuid

    import anyio
    anyio.run(run)


def test_add_day_success(test_setup: dict[str, any]) -> None:
    service = test_setup["service"]
    trip = test_setup["trip"]
    owner_id = test_setup["owner_id"]

    command = AddItineraryDayCommand(
        trip_id=str(trip.trip_id),
        requester_id=str(owner_id),
        day_number=1,
        title="Day 1",
        date=date(2027, 6, 1),
    )

    async def run() -> None:
        result = await service.add_day(command)
        assert isinstance(result, Success)
        assert len(result.value.days) == 1
        assert result.value.days[0].day_number == 1
        assert result.value.days[0].title == "Day 1"

    import anyio
    anyio.run(run)
