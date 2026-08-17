"""PlanningPreferences — user preferences for AI plan generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class PlanningPreferences(ValueObject):
    """
    Immutable value object capturing user preferences for plan generation.

    Validated at construction time - invalid preferences raise ValidationError.

    Attributes:
        destination:          Target city, region, or country (1-200 chars).
        duration_days:        Number of days for the trip (1-30).
        budget_level:         One of: budget, mid_range, luxury.
        interests:            Tuple of interest tags (e.g. 'history', 'food').
        travel_style:         One of: relaxed, balanced, active.
        special_requirements: Free-text requirements (dietary, accessibility, etc.).
    """

    destination: str
    duration_days: int
    budget_level: str
    interests: tuple[str, ...]
    travel_style: str
    special_requirements: str

    _VALID_BUDGET_LEVELS = frozenset({"budget", "mid_range", "luxury"})
    _VALID_TRAVEL_STYLES = frozenset({"relaxed", "balanced", "active"})

    def __post_init__(self) -> None:
        if not self.destination or not self.destination.strip():
            raise ValidationError(
                "Destination cannot be empty.", field="destination"
            )
        if len(self.destination) > 200:
            raise ValidationError(
                "Destination must be at most 200 characters.",
                field="destination",
                value=self.destination,
            )
        if self.duration_days < 1 or self.duration_days > 30:
            raise ValidationError(
                "Duration must be between 1 and 30 days.",
                field="duration_days",
                value=self.duration_days,
            )
        if self.budget_level not in self._VALID_BUDGET_LEVELS:
            raise ValidationError(
                f"Invalid budget level: '{self.budget_level}'. "
                f"Valid values: {sorted(self._VALID_BUDGET_LEVELS)}.",
                field="budget_level",
                value=self.budget_level,
            )
        if self.travel_style not in self._VALID_TRAVEL_STYLES:
            raise ValidationError(
                f"Invalid travel style: '{self.travel_style}'. "
                f"Valid values: {sorted(self._VALID_TRAVEL_STYLES)}.",
                field="travel_style",
                value=self.travel_style,
            )
