"""Domain service interfaces for travel recommendations."""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.modules.travel.recommendations.domain.entities.recommendation import (
    ActivityRecommendation,
    DestinationRecommendation,
    RestaurantRecommendation,
)
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences


class RecommendationEngine(Protocol):
    """Protocol for generating personalized recommendations."""

    async def recommend_destinations(
        self,
        preferences: UserPreferences,
        limit: int = 10,
    ) -> list[DestinationRecommendation]:
        """Recommend destination locations based on user preferences."""
        ...

    async def recommend_activities(
        self,
        preferences: UserPreferences,
        trip_id: UUID,
        limit: int = 10,
    ) -> list[ActivityRecommendation]:
        """Recommend activities based on user preferences and current trip context."""
        ...

    async def recommend_restaurants(
        self,
        preferences: UserPreferences,
        trip_id: UUID,
        limit: int = 10,
    ) -> list[RestaurantRecommendation]:
        """Recommend restaurants based on user preferences and current trip context."""
        ...


class SimilarityEngine(Protocol):
    """Protocol for finding similar trips and content."""

    async def find_similar_trips(
        self,
        trip_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Find other trips that are similar to the specified trip ID."""
        ...


class RankingEngine(Protocol):
    """Protocol for ranking lists of items based on user preferences."""

    async def rank_items(
        self,
        items: list[Any],
        preferences: UserPreferences,
    ) -> list[Any]:
        """Rank a generic list of items in descending order of suitability."""
        ...


class PopularityProvider(Protocol):
    """Protocol for fetching globally trending/popular content."""

    async def get_popular_destinations(
        self,
        limit: int = 10,
    ) -> list[DestinationRecommendation]:
        """Fetch globally popular or trending destination recommendations."""
        ...
