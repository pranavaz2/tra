"""API endpoint tests for the AI Assistant presentation router."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.modules.travel.assistant.application.dtos import (
    ChatResponseDTO,
    ConfirmActionResultDTO,
    ConversationHistoryDTO,
    PersistedMessageDTO,
    ProposedActionDTO,
    RejectActionResultDTO,
    TravelWarningDTO,
    TripWarningsDTO,
)

from app.modules.travel.assistant.domain.enums import (
    ActionStatus,
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.infrastructure.dependencies import (
    get_assistant_service,
)
from app.modules.travel.assistant.presentation.router import router
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.result import Failure, Success

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())
ACTION_ID = str(uuid.uuid4())


def _auth_ctx() -> AuthorizationContext:
    now = datetime.now(UTC)
    return AuthorizationContext(
        user_id=USER_ID,
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


class _MockAssistantService:
    def __init__(self) -> None:
        self.chat_result = Success(
            ChatResponseDTO(
                message="Hello from Travix Assistant!",
                response_type=AssistantResponseType.INFORMATIONAL,
                proposed_action=None,
                tools_used=(AssistantActionType.READ_TRIP,),
            )
        )
        self.confirm_result = Success(
            ConfirmActionResultDTO(
                action=ProposedActionDTO(
                    action_id=uuid.UUID(ACTION_ID),
                    trip_id=uuid.UUID(TRIP_ID),
                    action_type=AssistantActionType.PROPOSE_ADDING_ACTIVITY,
                    summary="Add dinner",
                    description="Add dinner at 7pm",
                    payload={"title": "Dinner"},
                    status=ActionStatus.APPLIED,
                    created_at=datetime.now(UTC),
                    applied_at=datetime.now(UTC),
                ),
                itinerary=None,
                message="Action applied successfully.",
            )
        )
        self.reject_result = Success(
            RejectActionResultDTO(
                action=ProposedActionDTO(
                    action_id=uuid.UUID(ACTION_ID),
                    trip_id=uuid.UUID(TRIP_ID),
                    action_type=AssistantActionType.PROPOSE_ADDING_ACTIVITY,
                    summary="Add dinner",
                    description="Add dinner at 7pm",
                    payload={"title": "Dinner"},
                    status=ActionStatus.REJECTED,
                    created_at=datetime.now(UTC),
                ),
                message="Action cancelled.",
            )
        )

    async def chat(self, command):
        return self.chat_result

    async def confirm_action(self, command):
        return self.confirm_result

    async def get_history(self, query):
        return Success(
            ConversationHistoryDTO(
                conversation_id=uuid.UUID(TRIP_ID),
                trip_id=uuid.UUID(TRIP_ID),
                user_id=uuid.UUID(USER_ID),
                messages=(
                    PersistedMessageDTO(
                        message_id=uuid.uuid4(),
                        role="user",
                        content="Where should we go?",
                        response_type=None,
                        action_id=None,
                        tools_used=(),
                        created_at=datetime.now(UTC),
                    ),
                    PersistedMessageDTO(
                        message_id=uuid.uuid4(),
                        role="assistant",
                        content="You could visit Kiyomizu-dera.",
                        response_type=AssistantResponseType.INFORMATIONAL,
                        action_id=None,
                        tools_used=(AssistantActionType.READ_ITINERARY,),
                        created_at=datetime.now(UTC),
                    ),
                ),
            )
        )

    async def clear_history(self, command):
        return Success(None)

    async def get_warnings(self, trip_id: str, requester_id: str):
        return Success(
            TripWarningsDTO(
                trip_id=uuid.UUID(TRIP_ID),
                warnings=(
                    TravelWarningDTO(
                        warning_id="overlap_1",
                        category="timing",
                        severity="warning",
                        title="Schedule Overlap",
                        message="Activities overlap on Day 1.",
                        day_number=1,
                        item_ids=("item-1", "item-2"),
                        metadata={},
                    ),
                ),
                total_warnings=1,
                has_critical=False,
                itinerary_conflicts_count=1,
                budget_risks_count=0,
            )
        )


@pytest.fixture
def test_app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.mark.asyncio
async def test_get_history_endpoint_success(test_app):
    mock_service = _MockAssistantService()
    test_app.dependency_overrides[get_authorization_context] = _auth_ctx
    test_app.dependency_overrides[get_assistant_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/trips/{TRIP_ID}/assistant/history")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trip_id"] == TRIP_ID
    assert len(data["messages"]) == 2
    assert data["messages"][0]["content"] == "Where should we go?"


@pytest.mark.asyncio
async def test_clear_history_endpoint_success(test_app):
    mock_service = _MockAssistantService()
    test_app.dependency_overrides[get_authorization_context] = _auth_ctx
    test_app.dependency_overrides[get_assistant_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        resp = await client.delete(f"/api/v1/trips/{TRIP_ID}/assistant/history")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["cleared"] is True


@pytest.mark.asyncio
async def test_chat_endpoint_success(test_app):
    mock_service = _MockAssistantService()
    test_app.dependency_overrides[get_authorization_context] = _auth_ctx
    test_app.dependency_overrides[get_assistant_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v1/trips/{TRIP_ID}/assistant/chat",
            json={"message": "What is my next stop?", "history": []},
        )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["message"] == "Hello from Travix Assistant!"
    assert data["response_type"] == "informational"


@pytest.mark.asyncio
async def test_confirm_action_endpoint_success(test_app):
    mock_service = _MockAssistantService()
    test_app.dependency_overrides[get_authorization_context] = _auth_ctx
    test_app.dependency_overrides[get_assistant_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v1/trips/{TRIP_ID}/assistant/actions/{ACTION_ID}/confirm"
        )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["action"]["status"] == "applied"
    assert data["message"] == "Action applied successfully."


@pytest.mark.asyncio
async def test_confirm_action_endpoint_forbidden(test_app):
    mock_service = _MockAssistantService()
    mock_service.confirm_result = Failure(
        ForbiddenError("Viewers are not permitted to modify trip details.")
    )
    test_app.dependency_overrides[get_authorization_context] = _auth_ctx
    test_app.dependency_overrides[get_assistant_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/api/v1/trips/{TRIP_ID}/assistant/actions/{ACTION_ID}/confirm"
        )

    assert resp.status_code == 403
    data = resp.json()
    assert data["status"] == 403
    assert data["error_code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_get_trip_warnings_endpoint(test_app):
    mock_service = _MockAssistantService()
    test_app.dependency_overrides[get_authorization_context] = _auth_ctx
    test_app.dependency_overrides[get_assistant_service] = lambda: mock_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        resp = await client.get(f"/api/v1/trips/{TRIP_ID}/warnings")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["trip_id"] == TRIP_ID
    assert data["total_warnings"] == 1
    assert data["itinerary_conflicts_count"] == 1
    assert data["warnings"][0]["warning_id"] == "overlap_1"
    assert data["warnings"][0]["category"] == "timing"
    assert data["warnings"][0]["severity"] == "warning"

