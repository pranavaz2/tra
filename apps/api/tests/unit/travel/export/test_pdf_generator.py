"""Unit tests for the vector PDF 1.4 itinerary generator."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
import uuid
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.export.infrastructure.pdf_generator import (
    PdfGenerator,
    _escape_pdf_text,
)
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


@pytest.fixture
def sample_trip():
    trip_id = TripId(uuid.uuid4())
    owner_id = UserId(uuid.uuid4())
    return Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle("Tokyo Adventure"),
        privacy=TripPrivacy.PRIVATE,
    )


@pytest.fixture
def sample_itinerary(sample_trip):
    itin_id = ItineraryId(uuid.uuid4())
    day1_id = ItineraryDayId(uuid.uuid4())
    day2_id = ItineraryDayId(uuid.uuid4())

    act1 = ItineraryItem(
        entity_id=ItineraryItemId(uuid.uuid4()),
        day_id=day1_id,
        title=ItemTitle("Shibuya Crossing"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(9, 30),
        end_time=time(11, 0),
        description="Walk across the busiest intersection in the world.",
        cost=Decimal("0.00"),
        currency="USD",
    )
    act2 = ItineraryItem(
        entity_id=ItineraryItemId(uuid.uuid4()),
        day_id=day1_id,
        title=ItemTitle("Meiji Shrine Visit"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(13, 0),
        end_time=None,
        description="Peaceful wooded shrine grounds.",
        cost=Decimal("0.00"),
        currency="USD",
    )
    act3 = ItineraryItem(
        entity_id=ItineraryItemId(uuid.uuid4()),
        day_id=day2_id,
        title=ItemTitle("Akihabara Tech & Arcade Walk"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=None,
        end_time=None,
        description="Gaming centers and anime shops.",
        cost=Decimal("50.00"),
        currency="USD",
    )

    day1 = ItineraryDay(
        entity_id=day1_id,
        itinerary_id=itin_id,
        day_number=1,
        date=date(2026, 10, 1),
        title="Shibuya & Harajuku",
        items=[act1, act2],
    )
    day2 = ItineraryDay(
        entity_id=day2_id,
        itinerary_id=itin_id,
        day_number=2,
        date=date(2026, 10, 2),
        title="Akihabara & Ueno",
        items=[act3],
    )

    return Itinerary(
        entity_id=itin_id,
        trip_id=sample_trip.entity_id,
        days=[day1, day2],
        version=1,
    )


@pytest.fixture
def sample_budget(sample_trip):
    return TripBudget.create(
        budget_id=BudgetId(uuid.uuid4()),
        trip_id=sample_trip.entity_id,
        owner_id=sample_trip.owner_id,
        limit=Money(Decimal("3000.00"), "USD"),
    )


class TestPDFGenerator:
    """Test suite for vector PDF 1.4 generation."""

    def test_pdf_header_and_structure(self, sample_trip, sample_itinerary, sample_budget):
        pdf_bytes = PdfGenerator.generate(
            trip=sample_trip,
            itinerary=sample_itinerary,
            budget=sample_budget,
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 200
        # Valid PDF header
        assert pdf_bytes.startswith(b"%PDF-1.4")
        # Valid EOF marker
        assert b"%%EOF" in pdf_bytes
        # Catalog and Pages dict present
        assert b"/Type /Catalog" in pdf_bytes
        assert b"/Type /Pages" in pdf_bytes
        assert b"/Type /Page" in pdf_bytes

    def test_pdf_content_includes_trip_details(self, sample_trip, sample_itinerary):
        pdf_bytes = PdfGenerator.generate(
            trip=sample_trip,
            itinerary=sample_itinerary,
            budget=None,
        )

        assert b"Tokyo Adventure" in pdf_bytes
        assert b"Shibuya" in pdf_bytes
        assert b"Meiji Shrine" in pdf_bytes

    def test_pdf_with_budget_summary(self, sample_trip, sample_itinerary, sample_budget):
        pdf_bytes = PdfGenerator.generate(
            trip=sample_trip,
            itinerary=sample_itinerary,
            budget=sample_budget,
        )

        assert b"Budget Summary" in pdf_bytes
        assert b"3000.00" in pdf_bytes

    def test_pdf_without_itinerary_or_budget(self, sample_trip):
        pdf_bytes = PdfGenerator.generate(
            trip=sample_trip,
            itinerary=None,
            budget=None,
        )

        assert pdf_bytes.startswith(b"%PDF-1.4")
        assert b"Tokyo Adventure" in pdf_bytes
        assert b"No itinerary days scheduled yet" in pdf_bytes
        assert b"%%EOF" in pdf_bytes

    def test_escape_pdf_text(self):
        raw = "Hello (World) \\ with / slashes [and] brackets"
        escaped = _escape_pdf_text(raw)
        assert "\\(" in escaped
        assert "\\)" in escaped
        assert "\\\\" in escaped
