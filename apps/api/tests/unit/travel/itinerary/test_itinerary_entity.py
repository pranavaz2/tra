"""Unit tests for the Itinerary domain aggregate."""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

import pytest

from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.errors import (
    ItineraryAlreadyDeletedError,
    ItineraryDayAlreadyExistsError,
    ItineraryDayNotFoundError,
    ItineraryItemNotFoundError,
)
from app.shared.domain.errors import ValidationError


def _make_itinerary() -> Itinerary:
    return Itinerary.create(
        itinerary_id=ItineraryId(value=uuid.uuid4()),
        trip_id=TripId(value=uuid.uuid4()),
    )


def test_create_itinerary_sets_initial_fields() -> None:
    itinerary = _make_itinerary()
    assert itinerary.version == 1
    assert len(itinerary.days) == 0
    assert itinerary.is_deleted is False


def test_add_day_increases_version_and_adds_day() -> None:
    itinerary = _make_itinerary()
    day_id = ItineraryDayId(value=uuid.uuid4())
    day = itinerary.add_day(day_id=day_id, day_number=1, title="Day 1", date=date(2027, 6, 1))

    assert len(itinerary.days) == 1
    assert itinerary.days[0] == day
    assert day.day_number == 1
    assert day.title == "Day 1"
    assert day.date == date(2027, 6, 1)
    assert itinerary.version == 2


def test_add_day_invariants_enforced() -> None:
    itinerary = _make_itinerary()
    day_id1 = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day_id1, day_number=1)

    # Duplicate day number
    day_id2 = ItineraryDayId(value=uuid.uuid4())
    with pytest.raises(ItineraryDayAlreadyExistsError):
        itinerary.add_day(day_id=day_id2, day_number=1)

    # Invalid day number < 1
    day_id3 = ItineraryDayId(value=uuid.uuid4())
    with pytest.raises(ValidationError) as exc:
        itinerary.add_day(day_id=day_id3, day_number=0)
    assert exc.value.field == "day_number"


def test_add_days_keeps_sorted() -> None:
    itinerary = _make_itinerary()
    day_id1 = ItineraryDayId(value=uuid.uuid4())
    day_id2 = ItineraryDayId(value=uuid.uuid4())
    day_id3 = ItineraryDayId(value=uuid.uuid4())

    itinerary.add_day(day_id=day_id3, day_number=3)
    itinerary.add_day(day_id=day_id1, day_number=1)
    itinerary.add_day(day_id=day_id2, day_number=2)

    assert [d.day_number for d in itinerary.days] == [1, 2, 3]


def test_update_day_mutates_fields() -> None:
    itinerary = _make_itinerary()
    day_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day_id, day_number=1, title="Day 1")

    itinerary.update_day(day_id=day_id, day_number=2, title="Updated Day", date=date(2027, 6, 2))
    assert itinerary.days[0].day_number == 2
    assert itinerary.days[0].title == "Updated Day"
    assert itinerary.days[0].date == date(2027, 6, 2)


def test_remove_day_deletes_day() -> None:
    itinerary = _make_itinerary()
    day_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day_id, day_number=1)
    assert len(itinerary.days) == 1

    itinerary.remove_day(day_id)
    assert len(itinerary.days) == 0


def test_add_item_adds_item_to_correct_day() -> None:
    itinerary = _make_itinerary()
    day_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day_id, day_number=1)

    item_id = ItineraryItemId(value=uuid.uuid4())
    item = itinerary.add_item(
        item_id=item_id,
        day_id=day_id,
        title=ItemTitle("Breakfast at Cafe"),
        item_type=ItineraryItemType.RESTAURANT,
        start_time=time(8, 30),
        end_time=time(9, 30),
        cost=Decimal("15.50"),
        currency="USD",
    )

    assert len(itinerary.days[0].items) == 1
    assert itinerary.days[0].items[0] == item
    assert item.title.value == "Breakfast at Cafe"
    assert item.item_type == ItineraryItemType.RESTAURANT
    assert item.start_time == time(8, 30)
    assert item.cost == Decimal("15.50")


def test_update_item_can_move_item_to_other_day() -> None:
    itinerary = _make_itinerary()
    day1_id = ItineraryDayId(value=uuid.uuid4())
    day2_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day1_id, day_number=1)
    itinerary.add_day(day_id=day2_id, day_number=2)

    item_id = ItineraryItemId(value=uuid.uuid4())
    itinerary.add_item(
        item_id=item_id,
        day_id=day1_id,
        title=ItemTitle("Activity 1"),
        item_type=ItineraryItemType.ACTIVITY,
    )

    assert len(itinerary.days[0].items) == 1
    assert len(itinerary.days[1].items) == 0

    itinerary.update_item(
        item_id=item_id,
        day_id=day2_id,
        title=ItemTitle("Moved Activity"),
        item_type=ItineraryItemType.ACTIVITY,
    )

    assert len(itinerary.days[0].items) == 0
    assert len(itinerary.days[1].items) == 1
    assert itinerary.days[1].items[0].title.value == "Moved Activity"
    assert itinerary.days[1].items[0].day_id == day2_id


def test_remove_item_deletes_item() -> None:
    itinerary = _make_itinerary()
    day_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(day_id=day_id, day_number=1)

    item_id = ItineraryItemId(value=uuid.uuid4())
    itinerary.add_item(
        item_id=item_id,
        day_id=day_id,
        title=ItemTitle("Breakfast"),
        item_type=ItineraryItemType.RESTAURANT,
    )
    assert len(itinerary.days[0].items) == 1

    itinerary.remove_item(item_id)
    assert len(itinerary.days[0].items) == 0


def test_soft_delete_prevents_mutations() -> None:
    itinerary = _make_itinerary()
    itinerary.delete()

    assert itinerary.is_deleted is True
    assert itinerary.deleted_at is not None

    with pytest.raises(ItineraryAlreadyDeletedError):
        itinerary.add_day(day_id=ItineraryDayId(value=uuid.uuid4()), day_number=1)
