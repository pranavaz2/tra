"""Unit tests for Itinerary Pydantic schemas."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
import uuid

import pytest
from pydantic import ValidationError

from app.modules.travel.itinerary.presentation.schemas import (
    ItineraryDayCreateRequest,
    ItineraryDayUpdateRequest,
    ItineraryItemCreateRequest,
    ItineraryItemUpdateRequest,
)


def test_day_create_request_validation() -> None:
    # Valid request
    req = ItineraryDayCreateRequest(day_number=1, title="Day 1", date=date(2027, 6, 1))
    assert req.day_number == 1
    assert req.title == "Day 1"
    assert req.date == date(2027, 6, 1)

    # Invalid day_number (must be >= 1)
    with pytest.raises(ValidationError):
        ItineraryDayCreateRequest(day_number=0)

    # Too long title (max 100)
    with pytest.raises(ValidationError):
        ItineraryDayCreateRequest(day_number=1, title="a" * 101)


def test_item_create_request_validation() -> None:
    day_id = uuid.uuid4()
    # Valid request
    req = ItineraryItemCreateRequest(
        day_id=day_id,
        title="Dinner at Restaurant",
        item_type="restaurant",
        start_time=time(19, 0),
        end_time=time(21, 0),
        cost=Decimal("45.00"),
        currency="USD",
    )
    assert req.day_id == day_id
    assert req.title == "Dinner at Restaurant"
    assert req.item_type == "restaurant"
    assert req.start_time == time(19, 0)
    assert req.cost == Decimal("45.00")

    # Invalid item_type
    with pytest.raises(ValidationError):
        ItineraryItemCreateRequest(
            day_id=day_id,
            title="Dinner",
            item_type="invalid_type",
        )

    # Empty title
    with pytest.raises(ValidationError):
        ItineraryItemCreateRequest(
            day_id=day_id,
            title="",
            item_type="activity",
        )

    # Negative cost
    with pytest.raises(ValidationError):
        ItineraryItemCreateRequest(
            day_id=day_id,
            title="Breakfast",
            item_type="restaurant",
            cost=Decimal("-5.00"),
        )
