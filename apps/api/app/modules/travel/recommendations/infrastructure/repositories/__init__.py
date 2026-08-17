"""Infrastructure repositories package init for travel recommendations."""

from __future__ import annotations

from app.modules.travel.recommendations.infrastructure.repositories.preferences_repository import (
    SQLAlchemyUserPreferencesRepository,
)

__all__ = ["SQLAlchemyUserPreferencesRepository"]
