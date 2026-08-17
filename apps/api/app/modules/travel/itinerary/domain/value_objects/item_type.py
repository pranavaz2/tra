"""ItemType — Enum for canonical itinerary item types."""

from __future__ import annotations

import enum


class ItineraryItemType(str, enum.Enum):  # noqa: UP042
    """Canonical travel item categories."""

    ACTIVITY = "activity"
    TRANSPORT = "transport"
    LODGING = "lodging"
    RESTAURANT = "restaurant"
