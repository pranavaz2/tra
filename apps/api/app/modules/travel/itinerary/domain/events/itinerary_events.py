"""Itinerary domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ItineraryCreated(DomainEvent):
    """Emitted when a new Itinerary aggregate is created."""

    itinerary_id: str
    trip_id: str


@dataclass(frozen=True, kw_only=True)
class ItineraryDayAdded(DomainEvent):
    """Emitted when a day is added to an itinerary."""

    itinerary_id: str
    day_id: str
    day_number: int
    title: str | None
    date: date | None


@dataclass(frozen=True, kw_only=True)
class ItineraryDayUpdated(DomainEvent):
    """Emitted when an itinerary day is updated."""

    itinerary_id: str
    day_id: str
    day_number: int
    title: str | None
    date: date | None


@dataclass(frozen=True, kw_only=True)
class ItineraryDayRemoved(DomainEvent):
    """Emitted when an itinerary day is removed."""

    itinerary_id: str
    day_id: str


@dataclass(frozen=True, kw_only=True)
class ItineraryItemAdded(DomainEvent):
    """Emitted when an item is added to an itinerary day."""

    itinerary_id: str
    day_id: str
    item_id: str
    title: str
    item_type: str


@dataclass(frozen=True, kw_only=True)
class ItineraryItemUpdated(DomainEvent):
    """Emitted when an itinerary item is updated."""

    itinerary_id: str
    day_id: str
    item_id: str
    title: str
    item_type: str


@dataclass(frozen=True, kw_only=True)
class ItineraryItemRemoved(DomainEvent):
    """Emitted when an itinerary item is removed."""

    itinerary_id: str
    day_id: str
    item_id: str


@dataclass(frozen=True, kw_only=True)
class ItineraryDeleted(DomainEvent):
    """Emitted when an itinerary aggregate is soft-deleted."""

    itinerary_id: str
    trip_id: str
