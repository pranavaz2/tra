"""Push notification and preferences repository interfaces."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
import uuid

from app.modules.travel.notifications.domain.entities.device_token import (
    DevicePushToken,
)
from app.modules.travel.notifications.domain.entities.preferences import (
    NotificationPreferences,
)
from app.modules.travel.notifications.domain.entities.sent_notification import (
    SentNotificationLog,
)


@runtime_checkable
class IDeviceTokenRepository(Protocol):
    """Abstract port for managing registered device push tokens."""

    async def save(self, token: DevicePushToken) -> None:
        """Register or update a device push token."""
        ...

    async def delete_by_token(self, token: str) -> None:
        """Unregister a push token."""
        ...

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[DevicePushToken]:
        """List all active push tokens registered for a user."""
        ...

    async def list_by_user_ids(
        self, user_ids: list[uuid.UUID]
    ) -> list[DevicePushToken]:
        """List push tokens for a batch of users."""
        ...


@runtime_checkable
class INotificationPreferencesRepository(Protocol):
    """Abstract port for managing user notification preferences."""

    async def get_by_user_id(self, user_id: uuid.UUID) -> NotificationPreferences | None:
        """Retrieve user preferences, or None if not yet customized."""
        ...

    async def save(self, preferences: NotificationPreferences) -> None:
        """Persist or update user preferences."""
        ...


@runtime_checkable
class ISentNotificationRepository(Protocol):
    """Abstract port for tracking dispatched notifications across restarts."""

    async def exists_by_dedup_key(self, dedup_key: str) -> bool:
        """Check if notification with given dedup key was already dispatched."""
        ...

    async def save(self, log: SentNotificationLog) -> None:
        """Record dispatched notification."""
        ...
