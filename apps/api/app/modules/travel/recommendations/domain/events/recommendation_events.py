"""Domain events for travel recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class UserPreferencesUpdated(DomainEvent):
    """Event triggered when user preferences are created or updated."""

    user_id: str
    interests: list[str]
    dietary_preferences: list[str]
    travel_style: str
    travel_pace: str
    budget_tier: str
