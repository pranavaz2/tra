"""Domain value objects for travel recommendations."""

from __future__ import annotations

from app.modules.travel.recommendations.domain.value_objects.dietary_tag import DietaryTag
from app.modules.travel.recommendations.domain.value_objects.interest_tag import InterestTag
from app.modules.travel.recommendations.domain.value_objects.preferences_id import PreferencesId
from app.modules.travel.recommendations.domain.value_objects.recommendation_reason import (
    RecommendationReason,
)
from app.modules.travel.recommendations.domain.value_objects.recommendation_score import (
    RecommendationScore,
)

__all__ = [
    "DietaryTag",
    "InterestTag",
    "PreferencesId",
    "RecommendationReason",
    "RecommendationScore",
]
