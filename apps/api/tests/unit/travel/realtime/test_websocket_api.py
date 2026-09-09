"""WebSocket API endpoint tests for real-time trip synchronization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security.jwt.claims import AccessTokenClaims, DecodedAccessToken
from app.core.security.jwt.dependencies import get_jwt_service
from app.core.security.jwt.errors import JWTInvalidSignatureError
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.realtime.application.broadcaster import InMemoryTripConnectionManager
from app.modules.travel.realtime.infrastructure.dependencies import (
    get_trip_connection_manager,
    get_trip_read_repository,
    get_trip_sharing_repository,
)
from app.modules.travel.realtime.presentation.router import router as realtime_router
from app.modules.travel.sharing.domain.entities.trip_collaboration import TripCollaboration
from app.modules.travel.sharing.domain.entities.trip_member import TripMember
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.value_objects.collaboration_id import CollaborationId
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle


def create_decoded_token(user_id: str, email: str = "test@example.com") -> DecodedAccessToken:
    claims = AccessTokenClaims(
        sub=user_id,
        jti=str(uuid.uuid4()),
        iat=datetime.now(UTC),
        exp=datetime.now(UTC) + timedelta(minutes=15),
        nbf=datetime.now(UTC),
        iss="https://api.travix.ai",
        aud="travix-mobile",
        sid=str(uuid.uuid4()),
        email=email,
        verified=True,
    )
    return DecodedAccessToken(claims=claims, kid="test-key", algorithm="HS256", raw_token="raw")


def create_test_app(
    mock_trip_repo: MagicMock,
    mock_sharing_repo: MagicMock,
    mock_jwt_service: MagicMock,
    connection_manager: InMemoryTripConnectionManager,
) -> FastAPI:
    app = FastAPI()
    app.include_router(realtime_router, prefix="/api/v1")

    app.dependency_overrides[get_trip_read_repository] = lambda: mock_trip_repo
    app.dependency_overrides[get_trip_sharing_repository] = lambda: mock_sharing_repo
    app.dependency_overrides[get_jwt_service] = lambda: mock_jwt_service
    app.dependency_overrides[get_trip_connection_manager] = lambda: connection_manager

    return app


def test_ws_connection_missing_token():
    """Verify WebSocket is rejected with code 4001 when token query param is missing."""
    mock_trip_repo = MagicMock()
    mock_sharing_repo = MagicMock()
    mock_jwt_service = MagicMock()
    manager = InMemoryTripConnectionManager()

    app = create_test_app(mock_trip_repo, mock_sharing_repo, mock_jwt_service, manager)
    client = TestClient(app)

    trip_id = str(uuid.uuid4())
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/trips/{trip_id}/ws"):
            pass

    assert exc_info.value.code == 4001


def test_ws_connection_invalid_token():
    """Verify WebSocket is rejected with code 4001 when token is invalid."""
    mock_trip_repo = MagicMock()
    mock_sharing_repo = MagicMock()
    mock_jwt_service = MagicMock()
    mock_jwt_service.verify_access_token.side_effect = JWTInvalidSignatureError("Invalid signature")
    manager = InMemoryTripConnectionManager()

    app = create_test_app(mock_trip_repo, mock_sharing_repo, mock_jwt_service, manager)
    client = TestClient(app)

    trip_id = str(uuid.uuid4())
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/trips/{trip_id}/ws?token=invalid.jwt.token"):
            pass

    assert exc_info.value.code == 4001


def test_ws_connection_unauthorized_user():
    """Verify WebSocket is rejected with code 4003 when user has no permission on private trip."""
    mock_trip_repo = MagicMock()
    mock_sharing_repo = MagicMock()
    mock_jwt_service = MagicMock()
    manager = InMemoryTripConnectionManager()

    user_id = str(uuid.uuid4())
    owner_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    trip = Trip.create(
        trip_id=TripId(uuid.UUID(trip_id)),
        owner_id=UserId(uuid.UUID(owner_id)),
        title=TripTitle("Private Trip"),
        privacy=TripPrivacy.PRIVATE,
    )
    mock_trip_repo.find_by_id = AsyncMock(return_value=trip)
    mock_sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    mock_jwt_service.verify_access_token.return_value = create_decoded_token(user_id)

    app = create_test_app(mock_trip_repo, mock_sharing_repo, mock_jwt_service, manager)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/v1/trips/{trip_id}/ws?token=valid_token"):
            pass

    assert exc_info.value.code == 4003


def test_ws_connection_owner_success():
    """Verify trip owner successfully connects, receives presence.sync, and responds to ping."""
    mock_trip_repo = MagicMock()
    mock_sharing_repo = MagicMock()
    mock_jwt_service = MagicMock()
    manager = InMemoryTripConnectionManager()

    owner_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    trip = Trip.create(
        trip_id=TripId(uuid.UUID(trip_id)),
        owner_id=UserId(uuid.UUID(owner_id)),
        title=TripTitle("My Road Trip"),
        privacy=TripPrivacy.PRIVATE,
    )
    mock_trip_repo.find_by_id = AsyncMock(return_value=trip)
    mock_sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    mock_jwt_service.verify_access_token.return_value = create_decoded_token(owner_id, "owner@example.com")

    app = create_test_app(mock_trip_repo, mock_sharing_repo, mock_jwt_service, manager)
    client = TestClient(app)

    with client.websocket_connect(f"/api/v1/trips/{trip_id}/ws?token=owner_token") as ws:
        msg = ws.receive_json()
        assert msg["event_type"] == "presence.sync"
        assert msg["trip_id"] == trip_id
        assert len(msg["payload"]["collaborators"]) == 1
        assert msg["payload"]["collaborators"][0]["user_id"] == owner_id
        assert msg["payload"]["collaborators"][0]["role"] == "owner"

        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        assert pong["type"] == "pong"


def test_ws_connection_collaborator_editor():
    """Verify invited editor collaborator can connect to WebSocket."""
    mock_trip_repo = MagicMock()
    mock_sharing_repo = MagicMock()
    mock_jwt_service = MagicMock()
    manager = InMemoryTripConnectionManager()

    owner_id = str(uuid.uuid4())
    editor_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    trip = Trip.create(
        trip_id=TripId(uuid.UUID(trip_id)),
        owner_id=UserId(uuid.UUID(owner_id)),
        title=TripTitle("Collaborative Trip"),
        privacy=TripPrivacy.PRIVATE,
    )
    mock_trip_repo.find_by_id = AsyncMock(return_value=trip)

    collaboration = TripCollaboration.create(
        collaboration_id=CollaborationId(uuid.uuid4()),
        trip_id=TripId(uuid.UUID(trip_id)),
        owner_id=UserId(uuid.UUID(owner_id)),
        owner_member_id=MemberId(uuid.uuid4()),
    )
    collaboration.members.append(
        TripMember(
            entity_id=MemberId(uuid.uuid4()),
            user_id=UserId(uuid.UUID(editor_id)),
            role=MemberRole.EDITOR,
            joined_at=datetime.now(UTC),
        )
    )
    mock_sharing_repo.find_by_trip_id = AsyncMock(return_value=collaboration)

    mock_jwt_service.verify_access_token.return_value = create_decoded_token(editor_id, "editor@example.com")

    app = create_test_app(mock_trip_repo, mock_sharing_repo, mock_jwt_service, manager)
    client = TestClient(app)

    with client.websocket_connect(f"/api/v1/trips/{trip_id}/ws?token=editor_token") as ws:
        msg = ws.receive_json()
        assert msg["event_type"] == "presence.sync"
        assert any(c["user_id"] == editor_id and c["role"] == "editor" for c in msg["payload"]["collaborators"])
