"""Unit tests for ICalGenerator."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
import uuid

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.export.infrastructure.ical_generator import ICalGenerator
from app.modules.travel.itinerary.domain.entities.day import ItineraryDay
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle


def test_ical_generation_with_timed_and_all_day_items():
    """Verify ICalGenerator produces valid RFC 5545 output with start/end times and events."""
    trip_id = TripId(uuid.uuid4())
    owner_id = UserId(uuid.uuid4())
    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Tokyo & Kyoto Explorer"),
        privacy=TripPrivacy.PRIVATE,
    )

    itin_id = ItineraryId(uuid.uuid4())
    day1_id = ItineraryDayId(uuid.uuid4())
    day2_id = ItineraryDayId(uuid.uuid4())

    day1 = ItineraryDay(
        entity_id=day1_id,
        itinerary_id=itin_id,
        day_number=1,
        date=date(2026, 10, 15),
        title="Arrival in Tokyo",
        items=[
            ItineraryItem(
                entity_id=ItineraryItemId(uuid.uuid4()),
                day_id=day1_id,
                title=ItemTitle("Check in at Hotel"),
                item_type=ItineraryItemType.LODGING,
                start_time=time(15, 0),
                end_time=time(16, 0),
                description="Show booking confirmation",
                cost=Decimal("150.00"),
                currency="USD",
            )
        ],
    )

    day2 = ItineraryDay(
        entity_id=day2_id,
        itinerary_id=itin_id,
        day_number=2,
        date=date(2026, 10, 16),
        title="Kyoto Day Trip",
        items=[
            ItineraryItem(
                entity_id=ItineraryItemId(uuid.uuid4()),
                day_id=day2_id,
                title=ItemTitle("All day city exploration"),
                item_type=ItineraryItemType.ACTIVITY,
                start_time=None,
                end_time=None,
                description="Wander around Gion and Fushimi Inari",
                cost=None,
                currency=None,
            )
        ],
    )

    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        days=[day1, day2],
        version=1,
    )

    result = ICalGenerator.generate(trip=trip, itinerary=itinerary)

    assert "BEGIN:VCALENDAR" in result
    assert "VERSION:2.0" in result
    assert "PRODID:-//Travix AI//Travix Travel Itinerary//EN" in result
    assert "SUMMARY:Check in at Hotel" in result
    assert "SUMMARY:All day city exploration" in result
    assert "DTSTART:20261015T150000Z" in result
    assert "DTEND:20261015T160000Z" in result
    assert "VALUE=DATE:20261016" in result
    assert "END:VCALENDAR" in result


def test_ical_generation_empty_itinerary():
    """Verify ICalGenerator produces valid VCALENDAR even without days/items."""
    trip_id = TripId(uuid.uuid4())
    owner_id = UserId(uuid.uuid4())
    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Empty Weekend Trip"),
        privacy=TripPrivacy.PRIVATE,
    )

    result = ICalGenerator.generate(trip=trip, itinerary=None)

    assert "BEGIN:VCALENDAR" in result
    assert "VERSION:2.0" in result
    assert "X-WR-CALNAME:Empty Weekend Trip" in result
    assert "END:VCALENDAR" in result
