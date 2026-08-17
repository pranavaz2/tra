"""Repository interfaces for travel recommendations."""

from __future__ import annotations

from typing import Protocol

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences


class IUserPreferencesRepository(Protocol):
    """Protocol for UserPreferences database operations."""

    async def find_by_user_id(self, user_id: UserId) -> UserPreferences | None:
        """Find a user's travel preferences by their user ID."""
        ...

    async def save(self, preferences: UserPreferences) -> None:
        """Save/persist a user's travel preferences."""
        ...
