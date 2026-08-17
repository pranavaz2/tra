"""
Trip domain events.

All events are immutable facts emitted by the Trip aggregate after a
successful mutation. Consumers must not mutate events.

Subclass convention:
    DomainEvent uses @dataclass(frozen=True) WITHOUT kw_only=True, so its
    fields are positional. All subclasses here use kw_only=True to avoid
    "non-default argument follows default argument" errors from Python's
    dataclass inheritance rules.

    Construction:
        event = TripCreated(
            aggregate_id="<trip-uuid>",  # positional-or-keyword from DomainEvent
            trip_id="<trip-uuid>",        # keyword-only from this class
            ...
        )

All ID fields are plain str to keep events serialisable without importing
domain types — events may be published to an external event bus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class TripCreated(DomainEvent):
    """
    Emitted when a new Trip aggregate is created via Trip.create().

    Consumers may use this to:
      - Create an empty Itinerary for the new trip (Itinerary module).
      - Create a TripCollaboration record (Sharing module).
      - Write the initial TripSummaryProjection row (Projections module).

    aggregate_id: str(trip_id) — the newly created trip.
    """

    trip_id: str
    owner_id: str
    title: str
    status: str
    privacy: str
    departure_date: date | None = field(default=None)
    return_date: date | None = field(default=None)


@dataclass(frozen=True, kw_only=True)
class TripUpdated(DomainEvent):
    """
    Emitted when one or more non-status fields on a Trip are changed.

    changed_fields lists the names of the attributes that were mutated
    (e.g. ("title",), ("date_range",), ("privacy",)). Consumers that
    maintain projections use this to decide which columns to refresh.

    Status changes emit TripStatusChanged instead — they are distinct
    because they have different consumer reactions (notifications, access
    control recalculation, itinerary locking).

    aggregate_id: str(trip_id) — the trip that was updated.
    """

    trip_id: str
    changed_fields: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class TripStatusChanged(DomainEvent):
    """
    Emitted when Trip.transition_to() succeeds.

    Kept separate from TripUpdated so consumers can react to lifecycle
    transitions specifically (e.g., send departure reminders on ACTIVE,
    lock itinerary edits on COMPLETED, clean up proposals on ARCHIVED).

    aggregate_id: str(trip_id) — the trip whose status changed.
    """

    trip_id: str
    old_status: str
    new_status: str


@dataclass(frozen=True, kw_only=True)
class TripDeleted(DomainEvent):
    """
    Emitted when Trip.delete() performs a soft delete.

    Consumers may use this to:
      - Archive the Itinerary (Itinerary module).
      - Archive the TripBudget (Budget module).
      - Remove the trip from search indexes (Projections module).
      - Notify collaborators (Notifications module).

    aggregate_id: str(trip_id) — the trip that was deleted.
    """

    trip_id: str
    owner_id: str
    deleted_at: datetime
