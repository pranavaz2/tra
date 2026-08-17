"""Application queries for travel recommendations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GetRecommendationsQuery:
    """Query to get personalized recommendations for a user."""

    user_id: str
    trip_id: str | None = None
    limit: int = 10


@dataclass(frozen=True)
class GetTrendingDestinationsQuery:
    """Query to get trending/popular destinations."""

    limit: int = 10


@dataclass(frozen=True)
class GetNearbyRecommendationsQuery:
    """Query to get nearby recommendations based on a coordinate."""

    user_id: str
    latitude: float
    longitude: float
    radius_meters: int = 50000
    limit: int = 10


@dataclass(frozen=True)
class GetSimilarTripsQuery:
    """Query to get trips similar to a given trip ID."""

    trip_id: str
    limit: int = 10
