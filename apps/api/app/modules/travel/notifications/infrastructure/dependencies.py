"""Notifications dependency injection."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.dependencies import DatabaseSession
from app.modules.travel.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.travel.notifications.domain.provider import (
    IPushNotificationProvider,
)
from app.modules.travel.notifications.domain.repositories.interfaces import (
    IDeviceTokenRepository,
    INotificationPreferencesRepository,
    ISentNotificationRepository,
)
from app.modules.travel.notifications.infrastructure.providers.expo_provider import (
    ExpoPushNotificationProvider,
)
from app.modules.travel.notifications.infrastructure.repositories.device_token_repository import (
    SQLAlchemyDeviceTokenRepository,
)
from app.modules.travel.notifications.infrastructure.repositories.preferences_repository import (
    SQLAlchemyNotificationPreferencesRepository,
)
from app.modules.travel.notifications.infrastructure.repositories.sent_notification_repository import (
    SQLAlchemySentNotificationRepository,
)


@lru_cache(maxsize=1)
def get_push_notification_provider() -> IPushNotificationProvider:
    """Return the singleton push notification provider."""
    return ExpoPushNotificationProvider()


def get_device_token_repository(
    session: DatabaseSession,
) -> IDeviceTokenRepository:
    """Return device token repository instance."""
    return SQLAlchemyDeviceTokenRepository(session)


def get_notification_preferences_repository(
    session: DatabaseSession,
) -> INotificationPreferencesRepository:
    """Return notification preferences repository instance."""
    return SQLAlchemyNotificationPreferencesRepository(session)


def get_sent_notification_repository(
    session: DatabaseSession,
) -> ISentNotificationRepository:
    """Return sent notification repository instance."""
    return SQLAlchemySentNotificationRepository(session)


def get_notification_service(
    token_repo: Annotated[IDeviceTokenRepository, Depends(get_device_token_repository)],
    prefs_repo: Annotated[INotificationPreferencesRepository, Depends(get_notification_preferences_repository)],
    sent_repo: Annotated[ISentNotificationRepository, Depends(get_sent_notification_repository)],
    provider: Annotated[IPushNotificationProvider, Depends(get_push_notification_provider)],
) -> NotificationService:
    """Return NotificationService instance with all dependencies wired."""
    return NotificationService(
        token_repository=token_repo,
        provider=provider,
        preferences_repository=prefs_repo,
        sent_notification_repository=sent_repo,
    )


CurrentNotificationService = Annotated[
    NotificationService, Depends(get_notification_service)
]
