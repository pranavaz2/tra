"""Real-Time Presentation Layer — WebSocket Endpoints."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import WebSocketException

from app.core.security.jwt.dependencies import get_jwt_service
from app.core.security.jwt.errors import JWTError
from app.core.security.jwt.interfaces import JWTService
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.realtime.application.broadcaster import (
    InMemoryTripConnectionManager,
)
from app.modules.travel.realtime.domain.enums import EntityActionType, EntityType, RealtimeEventType
from app.modules.travel.realtime.domain.value_objects.realtime_event import TripRealtimeEvent
from app.modules.travel.realtime.infrastructure.dependencies import (
    get_trip_connection_manager,
    get_trip_read_repository,
    get_trip_sharing_repository,
)
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Real-Time Synchronization"])


async def _authenticate_and_authorize_ws(
    websocket: WebSocket,
    trip_id_str: str,
    token: str | None,
    jwt_service: JWTService,
    trip_repo: ITripRepository,
    sharing_repo: ITripCollaborationRepository,
) -> tuple[str, str, str] | None:
    """
    Validate JWT token and verify that the user is an owner, editor, or viewer of the trip.

    Returns (user_id, role, display_name) or None if unauthorized.
    """
    if not token:
        # Check Sec-WebSocket-Protocol header fallback
        protocols = websocket.headers.get("sec-websocket-protocol", "")
        if protocols:
            parts = [p.strip() for p in protocols.split(",")]
            for p in parts:
                if p.startswith("bearer."):
                    token = p[7:]
                    break
                elif p and p != "realtime":
                    token = p

    if not token:
        logger.warning("WebSocket connection rejected: missing auth token.")
        await websocket.close(code=4001, reason="Authentication token required.")
        return None

    try:
        decoded_token = jwt_service.verify_access_token(token)
        claims = decoded_token.claims
    except (JWTError, Exception) as exc:
        logger.warning("WebSocket authentication failed: %s", exc)
        await websocket.close(code=4001, reason="Invalid or expired token.")
        return None

    user_id_str = getattr(claims, "user_id", None) or getattr(claims, "sub", None)
    if not user_id_str:
        await websocket.close(code=4001, reason="Invalid token claims.")
        return None

    # Authorize against trip and collaboration repositories
    try:
        trip_id = TripId(uuid.UUID(trip_id_str))
        user_id = UserId(uuid.UUID(user_id_str))
    except Exception:
        await websocket.close(code=4004, reason="Invalid trip or user ID format.")
        return None

    try:
        trip = await trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            await websocket.close(code=4004, reason="Trip not found.")
            return None

        # Check Ownership
        if trip.owner_id == user_id:
            role = "owner"
        else:
            collab = await sharing_repo.find_by_trip_id(trip_id)
            role = None
            if collab:
                for member in collab.members:
                    if member.user_id == user_id:
                        role = member.role.value
                        break
                if not role and getattr(collab, "is_public", False):
                    role = "viewer"

            if not role and getattr(trip, "privacy", None) and trip.privacy.value == "public":
                role = "viewer"

            if not role:
                logger.warning(
                    "WebSocket access forbidden: user %s has no role on trip %s",
                    user_id_str,
                    trip_id_str,
                )
                await websocket.close(code=4003, reason="Forbidden: not a trip collaborator.")
                return None

    except Exception as exc:
        logger.error("Error during WebSocket authorization check: %s", exc)
        await websocket.close(code=4000, reason="Internal error verifying trip access.")
        return None

    email = getattr(claims, "email", "")
    display_name = email.split("@")[0] if email else f"User {user_id_str[:6]}"
    return user_id_str, role, display_name


@router.websocket("/trips/{trip_id}/ws")
@router.websocket("/trips/{trip_id}/realtime")
async def trip_realtime_websocket(
    websocket: WebSocket,
    trip_id: str,
    token: str | None = Query(default=None),
    connection_manager: InMemoryTripConnectionManager = Depends(get_trip_connection_manager),
    jwt_service: JWTService = Depends(get_jwt_service),
    trip_repo: ITripRepository = Depends(get_trip_read_repository),
    sharing_repo: ITripCollaborationRepository = Depends(get_trip_sharing_repository),
) -> None:
    """
    Trip-scoped WebSocket endpoint for live presence and multi-user change synchronization.

    Authentication:
        - Query param: `?token=<access_token>`
    """
    auth_result = await _authenticate_and_authorize_ws(
        websocket=websocket,
        trip_id_str=trip_id,
        token=token,
        jwt_service=jwt_service,
        trip_repo=trip_repo,
        sharing_repo=sharing_repo,
    )
    if auth_result is None:
        return

    user_id, role, display_name = auth_result
    connection_id = await connection_manager.connect(
        trip_id=trip_id,
        websocket=websocket,
        user_id=user_id,
        display_name=display_name,
        role=role,
    )

    try:
        # Main message loop: client keepalive ping/pong
        while True:
            raw_message = await websocket.receive_text()
            try:
                msg_data = json.loads(raw_message)
            except Exception:
                continue

            msg_type = msg_data.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now(UTC).isoformat()})
            elif msg_type == "pong":
                pass
            else:
                logger.debug("Received client ws message for trip %s: %s", trip_id, msg_type)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for user %s on trip %s", user_id, trip_id)
    except Exception as exc:
        logger.warning("WebSocket error for user %s on trip %s: %s", user_id, trip_id, exc)
    finally:
        await connection_manager.disconnect(
            trip_id=trip_id,
            user_id=user_id,
            connection_id=connection_id,
        )
