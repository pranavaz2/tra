"""Unit tests for the Travel Planning value objects."""

from __future__ import annotations

import pytest

from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.shared.domain.errors import ValidationError


def test_valid_preferences_creation() -> None:
    prefs = PlanningPreferences(
        destination="Rome",
        duration_days=5,
        budget_level="mid_range",
        interests=("history", "art"),
        travel_style="balanced",
        special_requirements="none",
    )
    assert prefs.destination == "Rome"
    assert prefs.duration_days == 5
    assert prefs.budget_level == "mid_range"


def test_empty_destination_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PlanningPreferences(
            destination="   ",
            duration_days=5,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        )
    assert exc_info.value.field == "destination"


def test_excessive_destination_length_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PlanningPreferences(
            destination="a" * 201,
            duration_days=5,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        )
    assert exc_info.value.field == "destination"


def test_invalid_duration_days_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PlanningPreferences(
            destination="Rome",
            duration_days=31,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        )
    assert exc_info.value.field == "duration_days"

    with pytest.raises(ValidationError) as exc_info:
        PlanningPreferences(
            destination="Rome",
            duration_days=0,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        )
    assert exc_info.value.field == "duration_days"


def test_invalid_budget_level_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PlanningPreferences(
            destination="Rome",
            duration_days=5,
            budget_level="super_luxury",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        )
    assert exc_info.value.field == "budget_level"


def test_invalid_travel_style_raises_validation_error() -> None:
    with pytest.raises(ValidationError) as exc_info:
        PlanningPreferences(
            destination="Rome",
            duration_days=5,
            budget_level="mid_range",
            interests=(),
            travel_style="extreme",
            special_requirements="",
        )
    assert exc_info.value.field == "travel_style"
