"""Domain repositories package init for travel recommendations."""

from __future__ import annotations

from app.modules.travel.recommendations.domain.repositories.interfaces import (
    IUserPreferencesRepository,
)

__all__ = ["IUserPreferencesRepository"]
