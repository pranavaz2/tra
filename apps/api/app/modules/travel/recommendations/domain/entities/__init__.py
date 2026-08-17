"""Domain entities for travel recommendations."""

from __future__ import annotations

from app.modules.travel.recommendations.domain.entities.recommendation import (
    ActivityRecommendation,
    DestinationRecommendation,
    Recommendation,
    RestaurantRecommendation,
)
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences

__all__ = [
    "ActivityRecommendation",
    "DestinationRecommendation",
    "Recommendation",
    "RestaurantRecommendation",
    "UserPreferences",
]
