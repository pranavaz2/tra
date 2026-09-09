"""Unit tests for persistent notification deduplication and delivery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.modules.travel.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.travel.notifications.domain.entities.device_token import (
    DevicePushToken,
)
from app.modules.travel.notifications.domain.entities.preferences import (
    NotificationPreferences,
)
from app.modules.travel.notifications.domain.entities.sent_notification import (
    SentNotificationLog,
)
from app.modules.travel.notifications.domain.enums import NotificationCategory
from app.modules.travel.notifications.domain.provider import (
    IPushNotificationProvider,
    PushTicket,
)
from app.modules.travel.notifications.domain.repositories.interfaces import (
    IDeviceTokenRepository,
    INotificationPreferencesRepository,
    ISentNotificationRepository,
)


class InMemorySentNotificationRepo(ISentNotificationRepository):
    def __init__(self) -> None:
        self.records: dict[str, SentNotificationLog] = {}

    async def exists_by_dedup_key(self, dedup_key: str) -> bool:
        return dedup_key in self.records

    async def save(self, log: SentNotificationLog) -> None:
        self.records[log.dedup_key] = log


class InMemoryPreferencesRepo(INotificationPreferencesRepository):
    def __init__(self) -> None:
        self.prefs: dict[uuid.UUID, NotificationPreferences] = {}

    async def get_by_user_id(self, user_id: uuid.UUID) -> NotificationPreferences | None:
        return self.prefs.get(user_id)

    async def save(self, preferences: NotificationPreferences) -> None:
        self.prefs[preferences.user_id] = preferences


@pytest.mark.asyncio
async def test_categorized_notification_delivery_and_persistence():
    """Verify notification is dispatched, logged to DB, and deduplicated on subsequent calls."""
    token_repo = MagicMock(spec=IDeviceTokenRepository)
    user_id = uuid.uuid4()
    device = DevicePushToken.create(user_id=user_id, token="ExponentPushToken[abc12345]")
    token_repo.list_by_user_id = AsyncMock(return_value=[device])

    provider = MagicMock(spec=IPushNotificationProvider)
    provider.send_messages = AsyncMock(return_value=[PushTicket(status="ok")])

    sent_repo = InMemorySentNotificationRepo()
    prefs_repo = InMemoryPreferencesRepo()

    service = NotificationService(
        token_repository=token_repo,
        provider=provider,
        preferences_repository=prefs_repo,
        sent_notification_repository=sent_repo,
    )

    dedup_key = f"reminder:trip-1:24h:{user_id}"

    # First dispatch should succeed
    dispatched = await service.send_categorized_notification(
        user_id=user_id,
        category=NotificationCategory.TRIP_REMINDERS,
        dedup_key=dedup_key,
        title="Trip Starts Tomorrow!",
        body="Pack your bags.",
    )
    assert dispatched is True
    assert provider.send_messages.call_count == 1
    assert await sent_repo.exists_by_dedup_key(dedup_key) is True

    # Second dispatch with same dedup_key should be skipped
    dispatched_second = await service.send_categorized_notification(
        user_id=user_id,
        category=NotificationCategory.TRIP_REMINDERS,
        dedup_key=dedup_key,
        title="Trip Starts Tomorrow!",
        body="Pack your bags.",
    )
    assert dispatched_second is False
    assert provider.send_messages.call_count == 1  # No extra call


@pytest.mark.asyncio
async def test_server_restart_safe_deduplication():
    """Simulate server restart with empty memory cache but populated DB repo."""
    token_repo = MagicMock(spec=IDeviceTokenRepository)
    user_id = uuid.uuid4()
    device = DevicePushToken.create(user_id=user_id, token="ExponentPushToken[abc12345]")
    token_repo.list_by_user_id = AsyncMock(return_value=[device])

    provider = MagicMock(spec=IPushNotificationProvider)
    provider.send_messages = AsyncMock(return_value=[PushTicket(status="ok")])

    sent_repo = InMemorySentNotificationRepo()
    dedup_key = f"weather:alert:trip-1:2026-10-15:{user_id}"
    # Pre-populate sent log to simulate previous server run
    await sent_repo.save(
        SentNotificationLog.create(
            user_id=user_id,
            dedup_key=dedup_key,
            category=NotificationCategory.WEATHER_ALERTS,
            title="Old alert",
            body="Rain advisory",
        )
    )

    # New service instance (representing new server process after restart)
    service_after_restart = NotificationService(
        token_repository=token_repo,
        provider=provider,
        sent_notification_repository=sent_repo,
    )

    dispatched = await service_after_restart.send_categorized_notification(
        user_id=user_id,
        category=NotificationCategory.WEATHER_ALERTS,
        dedup_key=dedup_key,
        title="Heavy Rain Expected",
        body="Indoor activities recommended.",
    )
    assert dispatched is False
    assert provider.send_messages.call_count == 0


@pytest.mark.asyncio
async def test_muted_category_suppression():
    """Verify disabled notification category suppresses push dispatch."""
    token_repo = MagicMock(spec=IDeviceTokenRepository)
    user_id = uuid.uuid4()
    device = DevicePushToken.create(user_id=user_id, token="ExponentPushToken[abc12345]")
    token_repo.list_by_user_id = AsyncMock(return_value=[device])

    provider = MagicMock(spec=IPushNotificationProvider)
    provider.send_messages = AsyncMock(return_value=[PushTicket(status="ok")])

    sent_repo = InMemorySentNotificationRepo()
    prefs_repo = InMemoryPreferencesRepo()
    prefs = NotificationPreferences.default_for_user(user_id)
    prefs.budget_alerts = False  # User muted budget alerts
    await prefs_repo.save(prefs)

    service = NotificationService(
        token_repository=token_repo,
        provider=provider,
        preferences_repository=prefs_repo,
        sent_notification_repository=sent_repo,
    )

    dispatched = await service.send_categorized_notification(
        user_id=user_id,
        category=NotificationCategory.BUDGET_ALERTS,
        dedup_key="budget:threshold:90:trip-1",
        title="Budget 90% Exceeded",
        body="Consider adjusting expenses.",
    )
    assert dispatched is False
    assert provider.send_messages.call_count == 0
