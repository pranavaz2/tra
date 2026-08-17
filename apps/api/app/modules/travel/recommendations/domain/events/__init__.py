"""Domain events package init for travel recommendations."""

from __future__ import annotations

from app.modules.travel.recommendations.domain.events.recommendation_events import (
    UserPreferencesUpdated,
)

__all__ = ["UserPreferencesUpdated"]
