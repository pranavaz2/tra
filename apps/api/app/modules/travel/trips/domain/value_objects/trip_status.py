"""TripStatus enum and transition helpers."""

from __future__ import annotations

from enum import Enum


class TripStatus(str, Enum):
    """Lifecycle status of a Trip aggregate."""

    DRAFT = "draft"
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


# Allowed transitions. ARCHIVED is terminal — no outbound edges.
_VALID_TRANSITIONS: dict[TripStatus, frozenset[TripStatus]] = {
    TripStatus.DRAFT: frozenset({TripStatus.PLANNED, TripStatus.ARCHIVED}),
    TripStatus.PLANNED: frozenset({TripStatus.ACTIVE, TripStatus.DRAFT, TripStatus.ARCHIVED}),
    TripStatus.ACTIVE: frozenset({TripStatus.COMPLETED, TripStatus.ARCHIVED}),
    TripStatus.COMPLETED: frozenset({TripStatus.ARCHIVED}),
    TripStatus.ARCHIVED: frozenset(),
}


def can_transition(from_status: TripStatus, to_status: TripStatus) -> bool:
    """Return True if transitioning from_status → to_status is permitted."""
    return to_status in _VALID_TRANSITIONS.get(from_status, frozenset())


def valid_next_statuses(status: TripStatus) -> frozenset[TripStatus]:
    """Return the set of statuses reachable from status in one step."""
    return _VALID_TRANSITIONS.get(status, frozenset())
