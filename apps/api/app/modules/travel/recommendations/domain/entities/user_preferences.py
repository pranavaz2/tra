"""UserPreferences aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.recommendations.domain.enums.budget_tier import BudgetTier
from app.modules.travel.recommendations.domain.enums.travel_pace import TravelPace
from app.modules.travel.recommendations.domain.enums.travel_style import TravelStyle
from app.modules.travel.recommendations.domain.events.recommendation_events import (
    UserPreferencesUpdated,
)
from app.modules.travel.recommendations.domain.value_objects.dietary_tag import DietaryTag
from app.modules.travel.recommendations.domain.value_objects.interest_tag import InterestTag
from app.modules.travel.recommendations.domain.value_objects.preferences_id import PreferencesId
from app.shared.domain.aggregate import AggregateRoot
from app.shared.domain.errors import ValidationError


@dataclass(kw_only=True, eq=False)
class UserPreferences(AggregateRoot[PreferencesId]):
    """
    UserPreferences aggregate root.

    Represents a user's core travel preferences.
    """

    user_id: UserId
    interests: list[InterestTag] = field(default_factory=list)
    dietary_preferences: list[DietaryTag] = field(default_factory=list)
    travel_style: TravelStyle = TravelStyle.CULTURE
    travel_pace: TravelPace = TravelPace.MEDIUM
    budget_tier: BudgetTier = BudgetTier.MID_RANGE
    version: int = 1
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        self._validate_interests(self.interests)
        self._validate_dietary_preferences(self.dietary_preferences)

    def _validate_interests(self, interests: list[InterestTag]) -> None:
        seen = set()
        for tag in interests:
            if tag.value in seen:
                raise ValidationError("Interests cannot contain duplicates.", field="interests")
            seen.add(tag.value)

    def _validate_dietary_preferences(self, dietary: list[DietaryTag]) -> None:
        seen = set()
        for tag in dietary:
            if tag.value in seen:
                raise ValidationError(
                    "Dietary tags cannot contain duplicates.", field="dietary_preferences"
                )
            seen.add(tag.value)

    @classmethod
    def create(
        cls,
        *,
        preferences_id: PreferencesId,
        user_id: UserId,
        interests: list[InterestTag],
        dietary_preferences: list[DietaryTag],
        travel_style: TravelStyle,
        travel_pace: TravelPace,
        budget_tier: BudgetTier,
    ) -> UserPreferences:
        """Create a new UserPreferences aggregate root."""
        preferences = cls(
            entity_id=preferences_id,
            user_id=user_id,
            interests=interests,
            dietary_preferences=dietary_preferences,
            travel_style=travel_style,
            travel_pace=travel_pace,
            budget_tier=budget_tier,
            version=1,
        )

        preferences.push_event(
            UserPreferencesUpdated(
                aggregate_id=str(preferences_id),
                user_id=str(user_id),
                interests=[tag.value for tag in interests],
                dietary_preferences=[tag.value for tag in dietary_preferences],
                travel_style=travel_style.value,
                travel_pace=travel_pace.value,
                budget_tier=budget_tier.value,
            )
        )

        return preferences

    def update(
        self,
        *,
        interests: list[InterestTag],
        dietary_preferences: list[DietaryTag],
        travel_style: TravelStyle,
        travel_pace: TravelPace,
        budget_tier: BudgetTier,
    ) -> None:
        """Update UserPreferences."""
        self._validate_interests(interests)
        self._validate_dietary_preferences(dietary_preferences)

        object.__setattr__(self, "interests", interests)
        object.__setattr__(self, "dietary_preferences", dietary_preferences)
        object.__setattr__(self, "travel_style", travel_style)
        object.__setattr__(self, "travel_pace", travel_pace)
        object.__setattr__(self, "budget_tier", budget_tier)
        object.__setattr__(self, "updated_at", datetime.now(UTC))

        self.push_event(
            UserPreferencesUpdated(
                aggregate_id=str(self.entity_id),
                user_id=str(self.user_id),
                interests=[tag.value for tag in interests],
                dietary_preferences=[tag.value for tag in dietary_preferences],
                travel_style=travel_style.value,
                travel_pace=travel_pace.value,
                budget_tier=budget_tier.value,
            )
        )
