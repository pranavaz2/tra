"""Unit tests for NotificationService."""

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
from app.modules.travel.notifications.domain.repositories.interfaces import (
    IDeviceTokenRepository,
)
from app.modules.travel.notifications.infrastructure.providers.expo_provider import (
    MockPushNotificationProvider,
)


class FakeDeviceTokenRepository(IDeviceTokenRepository):
    def __init__(self) -> None:
        self.tokens: dict[str, DevicePushToken] = {}

    async def save(self, token: DevicePushToken) -> None:
        self.tokens[token.token] = token

    async def delete_by_token(self, token: str) -> None:
        self.tokens.pop(token, None)

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[DevicePushToken]:
        return [t for t in self.tokens.values() if t.user_id == user_id]

    async def list_by_user_ids(
        self, user_ids: list[uuid.UUID]
    ) -> list[DevicePushToken]:
        return [t for t in self.tokens.values() if t.user_id in user_ids]


@pytest.mark.asyncio
async def test_register_and_remove_device_token():
    """Verify registering a device push token and removing on logout."""
    repo = FakeDeviceTokenRepository()
    provider = MockPushNotificationProvider()
    service = NotificationService(token_repository=repo, provider=provider)

    user_id = uuid.uuid4()
    token_str = "ExponentPushToken[abc123xyz]"

    registered = await service.register_device_token(
        user_id=user_id,
        token=token_str,
        platform="expo",
        device_name="iPhone 15 Pro",
    )

    assert registered.token == token_str
    user_tokens = await repo.list_by_user_id(user_id)
    assert len(user_tokens) == 1
    assert user_tokens[0].token == token_str

    # Remove token
    await service.remove_device_token(token_str)
    assert len(await repo.list_by_user_id(user_id)) == 0


@pytest.mark.asyncio
async def test_notify_users_actor_filtering_and_deduplication():
    """Verify notify_users excludes the initiating actor and prevents duplicate pushes."""
    repo = FakeDeviceTokenRepository()
    provider = MockPushNotificationProvider()
    service = NotificationService(token_repository=repo, provider=provider)

    actor_id = uuid.uuid4()
    collaborator_id = uuid.uuid4()

    await service.register_device_token(
        user_id=actor_id,
        token="ExponentPushToken[actor_token]",
    )
    await service.register_device_token(
        user_id=collaborator_id,
        token="ExponentPushToken[collaborator_token]",
    )

    # Dispatch notification for an itinerary update initiated by actor_id
    dispatched = await service.notify_users(
        event_id="evt-100",
        recipient_user_ids=[actor_id, collaborator_id],
        title="Day 2 Updated",
        body="New dinner reservation added",
        actor_id=actor_id,
    )

    assert dispatched == 1
    assert len(provider.sent_messages) == 1
    assert provider.sent_messages[0].to == "ExponentPushToken[collaborator_token]"
    assert provider.sent_messages[0].title == "Day 2 Updated"

    # Second call with the same event_id should be skipped by deduplication
    dispatched_second = await service.notify_users(
        event_id="evt-100",
        recipient_user_ids=[actor_id, collaborator_id],
        title="Day 2 Updated",
        body="New dinner reservation added",
        actor_id=actor_id,
    )

    assert dispatched_second == 0
    assert len(provider.sent_messages) == 1
