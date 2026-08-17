"""Itinerary application queries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetItineraryQuery:
    """Query to fetch the itinerary (including days and items) for a trip."""

    trip_id: str
    requester_id: str
