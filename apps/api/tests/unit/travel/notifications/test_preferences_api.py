"""API endpoint tests for Notification Preferences."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
from app.modules.travel.notifications.domain.entities.preferences import (
    NotificationPreferences,
)
from app.modules.travel.notifications.infrastructure.dependencies import (
    get_notification_service,
)
from app.modules.travel.notifications.presentation.router import router as notifications_router


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
async def test_get_preferences_api():
    """Verify GET /api/v1/notifications/preferences returns user settings."""
    user_id = str(uuid.uuid4())
    mock_service = MagicMock(spec=NotificationService)
    prefs = NotificationPreferences.default_for_user(uuid.UUID(user_id))
    mock_service.get_preferences = AsyncMock(return_value=prefs)

    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1")
    app.dependency_overrides[get_notification_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/notifications/preferences")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["user_id"] == user_id
    assert data["push_enabled"] is True
    assert data["budget_alerts"] is True


@pytest.mark.asyncio
async def test_patch_preferences_api():
    """Verify PATCH /api/v1/notifications/preferences updates settings."""
    user_id = str(uuid.uuid4())
    mock_service = MagicMock(spec=NotificationService)
    updated_prefs = NotificationPreferences.default_for_user(uuid.UUID(user_id))
    updated_prefs.budget_alerts = False
    mock_service.update_preferences = AsyncMock(return_value=updated_prefs)

    app = FastAPI()
    app.include_router(notifications_router, prefix="/api/v1")
    app.dependency_overrides[get_notification_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/api/v1/notifications/preferences",
            json={"budget_alerts": False},
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["budget_alerts"] is False
