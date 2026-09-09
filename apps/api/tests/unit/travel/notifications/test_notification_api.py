"""API endpoint tests for Push Notifications router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.modules.travel.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.travel.notifications.domain.entities.device_token import (
    DevicePushToken,
)
from app.modules.travel.notifications.infrastructure.dependencies import (
    get_notification_service,
)
from app.modules.travel.notifications.presentation.router import router as notifications_router


from datetime import UTC, datetime, timedelta


def create_auth_context(user_id: str) -> AuthorizationContext:
    now = datetime.now(UTC)
    return AuthorizationContext(
        user_id=user_id,
        session_id=str(uuid.uuid4()),
        token_id=str(uuid.uuid4()),
        token_version=1,
        session_version=1,
        authentication_method="password",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        email="test@example.com",
        is_email_verified=True,
    )


@pytest.mark.asyncio
async def test_register_device_token_api():
    """Verify POST /api/v1/notifications/devices registers token."""
    user_id = str(uuid.uuid4())
    token_str = "ExponentPushToken[unit_test_token_123]"

    mock_service = MagicMock(spec=NotificationService)
    mock_service.register_device_token = AsyncMock(
        return_value=DevicePushToken.create(
            user_id=uuid.UUID(user_id),
            token=token_str,
            platform="expo",
            device_name="Pixel 8",
        )
    )

    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1")
    app.dependency_overrides[get_notification_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/notifications/devices",
            json={"token": token_str, "platform": "expo", "device_name": "Pixel 8"},
        )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["token"] == token_str
    assert data["platform"] == "expo"


@pytest.mark.asyncio
async def test_unregister_device_token_api():
    """Verify DELETE /api/v1/notifications/devices/{token} returns 204."""
    user_id = str(uuid.uuid4())
    token_str = "ExponentPushToken[unit_test_token_123]"

    mock_service = MagicMock(spec=NotificationService)
    mock_service.remove_device_token = AsyncMock()

    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1")
    app.dependency_overrides[get_notification_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete(f"/api/v1/notifications/devices/{token_str}")

    assert response.status_code == 204
    mock_service.remove_device_token.assert_awaited_once_with(token_str)
