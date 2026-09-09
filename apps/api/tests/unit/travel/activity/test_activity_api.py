"""API endpoint tests for Trip Activity Feed router."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.modules.travel.activity.application.activity_service import ActivityService
from app.modules.travel.activity.application.dtos import ActivityFeedPageDTO, ActivityLogDTO
from app.modules.travel.activity.infrastructure.dependencies import (
    get_activity_service,
)
from app.modules.travel.activity.presentation.router import router as activity_router
from app.shared.domain.errors import ForbiddenError, NotFoundError
from app.shared.domain.result import Failure, Success


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
async def test_get_trip_activities_api_success():
    """Verify GET /api/v1/trips/{trip_id}/activities returns 200 with data envelope."""
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    mock_service = MagicMock(spec=ActivityService)
    now = datetime.now(UTC)
    mock_service.get_trip_activities = AsyncMock(
        return_value=Success(
            ActivityFeedPageDTO(
                items=[
                    ActivityLogDTO(
                        activity_id=str(uuid.uuid4()),
                        trip_id=trip_id,
                        actor_id=user_id,
                        actor_name="Alice",
                        action="day_added",
                        entity_type="day",
                        entity_id="day-1",
                        title="Day 1 added",
                        description="Arrival day",
                        metadata={},
                        created_at=now,
                    )
                ],
                total=1,
                limit=50,
                offset=0,
                has_more=False,
            )
        )
    )

    app = FastAPI()
    app.include_router(activity_router, prefix="/api/v1")
    app.dependency_overrides[get_activity_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/trips/{trip_id}/activities")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["action"] == "day_added"


@pytest.mark.asyncio
async def test_get_trip_activities_api_forbidden():
    """Verify GET /api/v1/trips/{trip_id}/activities returns 403 on permission denial."""
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    mock_service = MagicMock(spec=ActivityService)
    mock_service.get_trip_activities = AsyncMock(
        return_value=Failure(ForbiddenError("Access denied"))
    )

    app = FastAPI()
    app.include_router(activity_router, prefix="/api/v1")
    app.dependency_overrides[get_activity_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/trips/{trip_id}/activities")

    assert response.status_code == 403
