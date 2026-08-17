"""Application DTOs for travel recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypeAlias

from app.modules.travel.recommendations.domain.entities.recommendation import (
    ActivityRecommendation,
    DestinationRecommendation,
    Recommendation,
    RestaurantRecommendation,
)
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences
from app.shared.domain.result import Result


@dataclass(frozen=True)
class UserPreferencesDTO:
    """DTO representing user travel preferences."""

    user_id: str
    interests: list[str]
    dietary_preferences: list[str]
    travel_style: str
    travel_pace: str
    budget_tier: str

    @classmethod
    def from_entity(cls, entity: UserPreferences) -> UserPreferencesDTO:
        """Create a UserPreferencesDTO from a domain UserPreferences entity."""
        return cls(
            user_id=str(entity.user_id),
            interests=[tag.value for tag in entity.interests],
            dietary_preferences=[tag.value for tag in entity.dietary_preferences],
            travel_style=entity.travel_style.value,
            travel_pace=entity.travel_pace.value,
            budget_tier=entity.budget_tier.value,
        )


@dataclass(frozen=True)
class RecommendationDTO:
    """DTO representing a single recommendation."""

    id: str
    title: str
    description: str | None
    score: int
    reason: str
    recommendation_type: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_entity(cls, entity: Recommendation) -> RecommendationDTO:
        """Create a RecommendationDTO from a domain Recommendation entity."""
        metadata: dict[str, Any] = {}
        rec_type = "generic"

        if isinstance(entity, DestinationRecommendation):
            rec_type = "destination"
            metadata = {
                "location_id": str(entity.location_id),
                "country_code": entity.country_code,
            }
        elif isinstance(entity, ActivityRecommendation):
            rec_type = "activity"
            metadata = {
                "activity_type": entity.activity_type,
                "trip_id": str(entity.trip_id) if entity.trip_id else None,
            }
        elif isinstance(entity, RestaurantRecommendation):
            rec_type = "restaurant"
            metadata = {
                "cuisine_type": entity.cuisine_type,
                "trip_id": str(entity.trip_id) if entity.trip_id else None,
            }

        return cls(
            id=str(entity.entity_id),
            title=entity.title,
            description=entity.description,
            score=int(entity.score.value),
            reason=str(entity.reason.value),
            recommendation_type=rec_type,
            metadata=metadata,
        )


@dataclass(frozen=True)
class SimilarTripDTO:
    """DTO representing a similar trip recommendation."""

    trip_id: str
    title: str
    score: int
    reason: str


@dataclass(frozen=True)
class RecommendationsListDTO:
    """DTO wrapping grouped recommendations."""

    destinations: list[RecommendationDTO] = field(default_factory=list)
    activities: list[RecommendationDTO] = field(default_factory=list)
    restaurants: list[RecommendationDTO] = field(default_factory=list)


UpdatePreferencesResult: TypeAlias = "Result[UserPreferencesDTO]"  # noqa: UP040
GetRecommendationsResult: TypeAlias = "Result[RecommendationsListDTO]"  # noqa: UP040
GetTrendingDestinationsResult: TypeAlias = "Result[list[RecommendationDTO]]"  # noqa: UP040
GetNearbyRecommendationsResult: TypeAlias = "Result[list[RecommendationDTO]]"  # noqa: UP040
GetSimilarTripsResult: TypeAlias = "Result[list[SimilarTripDTO]]"  # noqa: UP040
