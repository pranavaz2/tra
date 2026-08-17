"""Itinerary application commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal


@dataclass(frozen=True)
class CreateItineraryCommand:
    """Command to create a new empty itinerary for a trip."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class AddItineraryDayCommand:
    """Command to add a day to an itinerary."""

    trip_id: str
    requester_id: str
    day_number: int
    title: str | None = None
    date: date | None = None


@dataclass(frozen=True)
class UpdateItineraryDayCommand:
    """Command to update an existing itinerary day."""

    trip_id: str
    day_id: str
    requester_id: str
    day_number: int
    title: str | None = None
    date: date | None = None


@dataclass(frozen=True)
class RemoveItineraryDayCommand:
    """Command to remove a day from an itinerary."""

    trip_id: str
    day_id: str
    requester_id: str


@dataclass(frozen=True)
class AddItineraryItemCommand:
    """Command to add a scheduled item to a day."""

    trip_id: str
    day_id: str
    requester_id: str
    title: str
    item_type: str
    description: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    location_id: str | None = None
    cost: Decimal | None = None
    currency: str | None = None


@dataclass(frozen=True)
class UpdateItineraryItemCommand:
    """Command to update an itinerary item."""

    trip_id: str
    item_id: str
    requester_id: str
    day_id: str | None = None  # Non-None allows moving the item to another day
    title: str = ""
    item_type: str = ""
    description: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    location_id: str | None = None
    cost: Decimal | None = None
    currency: str | None = None


@dataclass(frozen=True)
class RemoveItineraryItemCommand:
    """Command to remove an itinerary item."""

    trip_id: str
    item_id: str
    requester_id: str
