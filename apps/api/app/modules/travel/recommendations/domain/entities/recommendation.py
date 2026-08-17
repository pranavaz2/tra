"""Recommendation entities."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.travel.recommendations.domain.value_objects.recommendation_reason import (
    RecommendationReason,
)
from app.modules.travel.recommendations.domain.value_objects.recommendation_score import (
    RecommendationScore,
)
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class Recommendation(Entity[UUID]):
    """Base recommendation entity."""

    title: str
    description: str | None = None
    score: RecommendationScore
    reason: RecommendationReason


@dataclass(kw_only=True, eq=False)
class DestinationRecommendation(Recommendation):
    """Destination recommendation details."""

    location_id: UUID
    country_code: str


@dataclass(kw_only=True, eq=False)
class ActivityRecommendation(Recommendation):
    """Activity recommendation details."""

    activity_type: str
    trip_id: UUID | None = None


@dataclass(kw_only=True, eq=False)
class RestaurantRecommendation(Recommendation):
    """Restaurant/dining recommendation details."""

    cuisine_type: str
    trip_id: UUID | None = None
