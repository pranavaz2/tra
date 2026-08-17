"""TravelPace enum."""

from __future__ import annotations

from enum import StrEnum


class TravelPace(StrEnum):
    """Pace of itinerary travel."""

    SLOW = "slow"
    MEDIUM = "medium"
    FAST = "fast"
