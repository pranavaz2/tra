"""Application commands for travel recommendations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UpdatePreferencesCommand:
    """Command to update user travel preferences."""

    user_id: str
    interests: list[str]
    dietary_preferences: list[str]
    travel_style: str
    travel_pace: str
    budget_tier: str
