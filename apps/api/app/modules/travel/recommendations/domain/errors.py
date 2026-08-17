"""Domain-specific errors for the travel recommendations module."""

from __future__ import annotations

from app.shared.domain.errors import TravixError


class UserPreferencesNotFoundError(TravixError):
    """Raised when user preferences cannot be found for a given user ID."""

    code: str = "user_preferences_not_found"

    def __init__(self, user_id: str) -> None:
        super().__init__(message=f"User preferences not found for user: {user_id}")
