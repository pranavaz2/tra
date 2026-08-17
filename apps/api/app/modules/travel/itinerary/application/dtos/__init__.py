"""Itinerary application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import TypeAlias
from uuid import UUID

from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.result import Result


@dataclass(frozen=True)
class ItineraryItemSummary:
    """Snapshot of an ItineraryItem entity."""

    item_id: ItineraryItemId
    day_id: ItineraryDayId
    title: str
    item_type: ItineraryItemType
    description: str | None
    start_time: time | None
    end_time: time | None
    location_id: UUID | None
    cost: Decimal | None
    currency: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ItineraryDaySummary:
    """Snapshot of an ItineraryDay entity containing its items."""

    day_id: ItineraryDayId
    day_number: int
    title: str | None
    date: date | None
    items: tuple[ItineraryItemSummary, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ItinerarySummary:
    """Snapshot of the complete Itinerary aggregate."""

    itinerary_id: ItineraryId
    trip_id: TripId
    days: tuple[ItineraryDaySummary, ...]
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


# ---------------------------------------------------------------------------
# Result type aliases — one per use case
# ---------------------------------------------------------------------------

GetItineraryResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
CreateItineraryResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
AddItineraryDayResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
UpdateItineraryDayResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
RemoveItineraryDayResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
AddItineraryItemResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
UpdateItineraryItemResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
RemoveItineraryItemResult: TypeAlias = "Result[ItinerarySummary]"  # noqa: UP040
