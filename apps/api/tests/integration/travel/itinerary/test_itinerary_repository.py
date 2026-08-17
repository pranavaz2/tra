"""Integration tests for SQLAlchemyItineraryRepository against real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.infrastructure.repositories.trip_repository import SQLAlchemyTripRepository
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.infrastructure.repositories.itinerary_repository import SQLAlchemyItineraryRepository

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# Helper: Setup a Trip record in the DB
# ─────────────────────────────────────────────────────────────────────────────


async def _create_trip(db_session: AsyncSession, owner_id: uuid.UUID) -> Trip:
    trip_repo = SQLAlchemyTripRepository(db_session)
    trip = Trip.create(
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=UserId(value=owner_id),
        title=TripTitle(value="Itinerary Test Trip"),
    )
    await trip_repo.save(trip)
    return trip


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


async def test_save_and_find_itinerary(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    # 1. Create trip
    trip = await _create_trip(db_session, trip_owner_id)

    # 2. Create itinerary
    repo = SQLAlchemyItineraryRepository(db_session)
    itinerary_id = ItineraryId(value=uuid.uuid4())
    itinerary = Itinerary.create(itinerary_id=itinerary_id, trip_id=trip.trip_id)

    # Add day
    day_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day_id, day_number=1, title="Arrival Day", date=date(2027, 6, 1))

    # Add item
    item_id = ItineraryItemId(value=uuid.uuid4())
    itinerary.add_item(
        item_id=item_id,
        day_id=day_id,
        title=ItemTitle("Check-in at Hotel"),
        item_type=ItineraryItemType.LODGING,
        start_time=time(15, 0),
        cost=Decimal("150.00"),
        currency="EUR",
    )

    await repo.save(itinerary)
    await db_session.flush()

    # 3. Retrieve and verify
    loaded = await repo.find_by_id(itinerary_id)
    assert loaded is not None
    assert loaded.itinerary_id == itinerary_id
    assert loaded.trip_id == trip.trip_id
    assert len(loaded.days) == 1
    assert loaded.days[0].day_id == day_id
    assert loaded.days[0].title == "Arrival Day"
    assert len(loaded.days[0].items) == 1
    assert loaded.days[0].items[0].item_id == item_id
    assert loaded.days[0].items[0].title.value == "Check-in at Hotel"
    assert loaded.days[0].items[0].cost == Decimal("150.00")


async def test_find_by_trip_id(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    trip = await _create_trip(db_session, trip_owner_id)
    repo = SQLAlchemyItineraryRepository(db_session)

    # Initially none
    loaded = await repo.find_by_trip_id(trip.trip_id)
    assert loaded is None

    # Save
    itinerary = Itinerary.create(itinerary_id=ItineraryId(value=uuid.uuid4()), trip_id=trip.trip_id)
    await repo.save(itinerary)
    await db_session.flush()

    loaded = await repo.find_by_trip_id(trip.trip_id)
    assert loaded is not None
    assert loaded.trip_id == trip.trip_id


async def test_collection_synchronization(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    trip = await _create_trip(db_session, trip_owner_id)
    repo = SQLAlchemyItineraryRepository(db_session)

    # 1. Save initially with 2 days
    itinerary = Itinerary.create(itinerary_id=ItineraryId(value=uuid.uuid4()), trip_id=trip.trip_id)
    day1_id = ItineraryDayId(value=uuid.uuid4())
    day2_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day1_id, day_number=1, title="Day One")
    itinerary.add_day(day_id=day2_id, day_number=2, title="Day Two")
    await repo.save(itinerary)
    await db_session.flush()

    # 2. Modify: remove day 1, update day 2 to day 1, add a new day 2
    loaded = await repo.find_by_id(itinerary.itinerary_id)
    assert loaded is not None
    loaded.remove_day(day1_id)
    loaded.update_day(day_id=day2_id, day_number=1, title="Updated Day One")
    
    day3_id = ItineraryDayId(value=uuid.uuid4())
    loaded.add_day(day_id=day3_id, day_number=2, title="Brand New Day Two")
    await repo.save(loaded)
    await db_session.flush()

    # 3. Reload and verify sync
    reloaded = await repo.find_by_id(itinerary.itinerary_id)
    assert reloaded is not None
    assert len(reloaded.days) == 2
    assert [d.day_id for d in reloaded.days] == [day2_id, day3_id]
    assert reloaded.days[0].title == "Updated Day One"
    assert reloaded.days[0].day_number == 1
    assert reloaded.days[1].title == "Brand New Day Two"
    assert reloaded.days[1].day_number == 2
