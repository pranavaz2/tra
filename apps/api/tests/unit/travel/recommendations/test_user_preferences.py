"""Unit tests for the UserPreferences aggregate root."""

from __future__ import annotations

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences
from app.modules.travel.recommendations.domain.enums.budget_tier import BudgetTier
from app.modules.travel.recommendations.domain.enums.travel_pace import TravelPace
from app.modules.travel.recommendations.domain.enums.travel_style import TravelStyle
from app.modules.travel.recommendations.domain.events.recommendation_events import (
    UserPreferencesUpdated,
)
from app.modules.travel.recommendations.domain.value_objects.dietary_tag import DietaryTag
from app.modules.travel.recommendations.domain.value_objects.interest_tag import InterestTag
from app.modules.travel.recommendations.domain.value_objects.preferences_id import PreferencesId
from app.shared.domain.errors import ValidationError


def test_user_preferences_creation_success() -> None:
    """Preferences should be created successfully with correct properties and update events."""
    pid = PreferencesId.generate()
    uid = UserId.generate()
    interests = [InterestTag("culture"), InterestTag("food")]
    dietary = [DietaryTag("vegan")]

    preferences = UserPreferences.create(
        preferences_id=pid,
        user_id=uid,
        interests=interests,
        dietary_preferences=dietary,
        travel_style=TravelStyle.FOOD,
        travel_pace=TravelPace.FAST,
        budget_tier=BudgetTier.LUXURY,
    )

    assert preferences.entity_id == pid
    assert preferences.user_id == uid
    assert preferences.interests == interests
    assert preferences.dietary_preferences == dietary
    assert preferences.travel_style == TravelStyle.FOOD
    assert preferences.travel_pace == TravelPace.FAST
    assert preferences.budget_tier == BudgetTier.LUXURY
    assert preferences.version == 1

    events = preferences.pop_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, UserPreferencesUpdated)
    assert event.aggregate_id == str(pid)
    assert event.user_id == str(uid)
    assert event.interests == ["culture", "food"]
    assert event.dietary_preferences == ["vegan"]
    assert event.travel_style == "food"
    assert event.travel_pace == "fast"
    assert event.budget_tier == "luxury"


def test_user_preferences_creation_rejects_duplicate_interests() -> None:
    """Creating preferences with duplicate interest tags should raise ValidationError."""
    pid = PreferencesId.generate()
    uid = UserId.generate()
    interests = [InterestTag("culture"), InterestTag("culture")]

    with pytest.raises(ValidationError, match="Interests cannot contain duplicates"):
        UserPreferences.create(
            preferences_id=pid,
            user_id=uid,
            interests=interests,
            dietary_preferences=[],
            travel_style=TravelStyle.CULTURE,
            travel_pace=TravelPace.MEDIUM,
            budget_tier=BudgetTier.MID_RANGE,
        )


def test_user_preferences_creation_rejects_duplicate_dietary_tags() -> None:
    """Creating preferences with duplicate dietary tags should raise ValidationError."""
    pid = PreferencesId.generate()
    uid = UserId.generate()
    dietary = [DietaryTag("vegan"), DietaryTag("vegan")]

    with pytest.raises(ValidationError, match="Dietary tags cannot contain duplicates"):
        UserPreferences.create(
            preferences_id=pid,
            user_id=uid,
            interests=[],
            dietary_preferences=dietary,
            travel_style=TravelStyle.CULTURE,
            travel_pace=TravelPace.MEDIUM,
            budget_tier=BudgetTier.MID_RANGE,
        )


def test_user_preferences_update_success() -> None:
    """Updating preferences should mutate properties correctly and fire updated event."""
    pid = PreferencesId.generate()
    uid = UserId.generate()
    preferences = UserPreferences.create(
        preferences_id=pid,
        user_id=uid,
        interests=[InterestTag("nature")],
        dietary_preferences=[DietaryTag("gluten-free")],
        travel_style=TravelStyle.NATURE,
        travel_pace=TravelPace.SLOW,
        budget_tier=BudgetTier.BUDGET,
    )
    # Clear creation events
    preferences.pop_events()

    new_interests = [InterestTag("nature"), InterestTag("shopping")]
    new_dietary = [DietaryTag("vegetarian")]

    preferences.update(
        interests=new_interests,
        dietary_preferences=new_dietary,
        travel_style=TravelStyle.SHOPPING,
        travel_pace=TravelPace.MEDIUM,
        budget_tier=BudgetTier.MID_RANGE,
    )

    assert preferences.interests == new_interests
    assert preferences.dietary_preferences == new_dietary
    assert preferences.travel_style == TravelStyle.SHOPPING
    assert preferences.travel_pace == TravelPace.MEDIUM
    assert preferences.budget_tier == BudgetTier.MID_RANGE

    events = preferences.pop_events()
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, UserPreferencesUpdated)
    assert event.interests == ["nature", "shopping"]
    assert event.dietary_preferences == ["vegetarian"]
    assert event.travel_style == "shopping"
    assert event.travel_pace == "medium"
    assert event.budget_tier == "mid_range"


def test_user_preferences_update_rejects_duplicate_interests() -> None:
    """Updating preferences with duplicate interests should raise ValidationError."""
    pid = PreferencesId.generate()
    uid = UserId.generate()
    preferences = UserPreferences.create(
        preferences_id=pid,
        user_id=uid,
        interests=[InterestTag("nature")],
        dietary_preferences=[],
        travel_style=TravelStyle.NATURE,
        travel_pace=TravelPace.SLOW,
        budget_tier=BudgetTier.BUDGET,
    )

    with pytest.raises(ValidationError, match="Interests cannot contain duplicates"):
        preferences.update(
            interests=[InterestTag("nature"), InterestTag("nature")],
            dietary_preferences=[],
            travel_style=TravelStyle.NATURE,
            travel_pace=TravelPace.SLOW,
            budget_tier=BudgetTier.BUDGET,
        )


def test_user_preferences_update_rejects_duplicate_dietary_tags() -> None:
    """Updating preferences with duplicate dietary tags should raise ValidationError."""
    pid = PreferencesId.generate()
    uid = UserId.generate()
    preferences = UserPreferences.create(
        preferences_id=pid,
        user_id=uid,
        interests=[],
        dietary_preferences=[DietaryTag("vegan")],
        travel_style=TravelStyle.NATURE,
        travel_pace=TravelPace.SLOW,
        budget_tier=BudgetTier.BUDGET,
    )

    with pytest.raises(ValidationError, match="Dietary tags cannot contain duplicates"):
        preferences.update(
            interests=[],
            dietary_preferences=[DietaryTag("vegan"), DietaryTag("vegan")],
            travel_style=TravelStyle.NATURE,
            travel_pace=TravelPace.SLOW,
            budget_tier=BudgetTier.BUDGET,
        )
