"""ProposedActivity — a single activity within a proposed day."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ProposedActivity(ValueObject):
    """
    An individual activity suggested by the AI planning engine.

    Immutable value object. Part of a ProposedDay which is part of a
    PlanningResult. Contains no identity — defined entirely by attributes.

    Attributes:
        title:              Activity name (e.g. "Visit the Colosseum").
        description:        Brief explanation of the activity.
        category:           Activity category (e.g. sightseeing, dining, transport).
        duration_minutes:   Estimated duration in minutes.
        estimated_cost:     Optional cost estimate as a formatted string (e.g. "$25").
        provider_place_id:  Verified provider place ID (from Google Places or Locations).
        place_name:         Canonical name of the verified place.
        formatted_address:  Full real-world address of the verified place.
        latitude:           Geographic latitude verified by the Places provider.
        longitude:          Geographic longitude verified by the Places provider.
        rating:             Verified rating from provider if available.
        is_verified:        Whether this place was grounded/verified against real places data.
    """

    title: str
    description: str
    category: str
    duration_minutes: int
    estimated_cost: str | None = None
    provider_place_id: str | None = None
    place_name: str | None = None
    formatted_address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    is_verified: bool = True
