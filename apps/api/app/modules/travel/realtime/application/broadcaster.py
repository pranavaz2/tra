"""Real-Time Event Broadcaster and WebSocket Connection Manager."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
from typing import Any, Protocol, runtime_checkable
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from app.modules.travel.realtime.domain.entities.presence import CollaboratorPresence
from app.modules.travel.realtime.domain.enums import (
    EntityActionType,
    EntityType,
    RealtimeEventType,
)
from app.modules.travel.realtime.domain.value_objects.realtime_event import (
    TripRealtimeEvent,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class ITripEventBroadcaster(Protocol):
    """Abstract port for broadcasting real-time trip events."""

    async def broadcast_to_trip(self, trip_id: str, event: TripRealtimeEvent) -> None:
        """Broadcast a structured domain/system event to all active clients viewing the trip."""
        ...


class InMemoryTripConnectionManager(ITripEventBroadcaster):
    """
    Manages active WebSocket connections and live collaborator presence per trip room.

    Thread-safe, handles multiple devices/tabs per user, and cleans up broken connections gracefully.
    """

    def __init__(self) -> None:
        # trip_id -> {connection_id: WebSocket}
        self._rooms: dict[str, dict[str, WebSocket]] = {}
        # trip_id -> {user_id: set of connection_ids}
        self._user_conns: dict[str, dict[str, set[str]]] = {}
        # trip_id -> {user_id: CollaboratorPresence}
        self._presences: dict[str, dict[str, CollaboratorPresence]] = {}
        self._lock = asyncio.Lock()

    async def connect(
        self,
        *,
        trip_id: str,
        user_id: str,
        websocket: WebSocket,
        role: str,
        display_name: str | None = None,
    ) -> str:
        """
        Register a new WebSocket connection for a user in a trip room.

        Returns connection_id and broadcasts presence.joined if this is the user's first connection.
        """
        connection_id = str(uuid.uuid4())
        user_name = display_name or f"User {user_id[:6]}"

        await websocket.accept()

        is_new_user_on_trip = False
        async with self._lock:
            if trip_id not in self._rooms:
                self._rooms[trip_id] = {}
                self._user_conns[trip_id] = {}
                self._presences[trip_id] = {}

            self._rooms[trip_id][connection_id] = websocket

            if user_id not in self._user_conns[trip_id]:
                self._user_conns[trip_id][user_id] = set()
                is_new_user_on_trip = True
                self._presences[trip_id][user_id] = CollaboratorPresence(
                    user_id=user_id,
                    display_name=user_name,
                    role=role,
                    joined_at=datetime.now(UTC),
                    client_id=connection_id,
                )

            self._user_conns[trip_id][user_id].add(connection_id)

        # 1. Send active presence list sync to the newly connected socket
        sync_event = TripRealtimeEvent.create(
            trip_id=trip_id,
            event_type=RealtimeEventType.PRESENCE_SYNC,
            entity_type=EntityType.PRESENCE,
            entity_id=trip_id,
            action=EntityActionType.SYNC,
            actor_id=user_id,
            payload={
                "collaborators": [
                    p.to_dict() for p in self.get_active_presence(trip_id)
                ],
                "connection_id": connection_id,
            },
        )
        try:
            await websocket.send_json(sync_event.to_dict())
        except Exception as exc:
            logger.debug("Failed to send initial presence sync to %s: %s", connection_id, exc)

        # 2. If newly joined, broadcast presence.joined to other trip participants
        if is_new_user_on_trip:
            join_event = TripRealtimeEvent.create(
                trip_id=trip_id,
                event_type=RealtimeEventType.PRESENCE_JOINED,
                entity_type=EntityType.PRESENCE,
                entity_id=user_id,
                action=EntityActionType.JOINED,
                actor_id=user_id,
                payload={
                    "user_id": user_id,
                    "display_name": user_name,
                    "role": role,
                    "joined_at": datetime.now(UTC).isoformat(),
                },
            )
            await self.broadcast_to_trip(trip_id, join_event, exclude_connection_id=connection_id)

        logger.info(
            "WebSocket connected [trip=%s, user=%s, conn=%s, role=%s]",
            trip_id,
            user_id,
            connection_id,
            role,
        )
        return connection_id

    async def disconnect(
        self,
        *,
        trip_id: str,
        user_id: str,
        connection_id: str,
    ) -> None:
        """Unregister a connection and broadcast presence.left when user has no remaining sockets."""
        user_left_entirely = False
        presence_removed: CollaboratorPresence | None = None

        async with self._lock:
            if trip_id in self._rooms:
                self._rooms[trip_id].pop(connection_id, None)

            if trip_id in self._user_conns and user_id in self._user_conns[trip_id]:
                self._user_conns[trip_id][user_id].discard(connection_id)
                if not self._user_conns[trip_id][user_id]:
                    self._user_conns[trip_id].pop(user_id, None)
                    presence_removed = self._presences.get(trip_id, {}).pop(user_id, None)
                    user_left_entirely = True

            # Cleanup empty trip rooms
            if trip_id in self._rooms and not self._rooms[trip_id]:
                self._rooms.pop(trip_id, None)
                self._user_conns.pop(trip_id, None)
                self._presences.pop(trip_id, None)

        if user_left_entirely and presence_removed:
            leave_event = TripRealtimeEvent.create(
                trip_id=trip_id,
                event_type=RealtimeEventType.PRESENCE_LEFT,
                entity_type=EntityType.PRESENCE,
                entity_id=user_id,
                action=EntityActionType.LEFT,
                actor_id=user_id,
                payload={
                    "user_id": user_id,
                    "display_name": presence_removed.display_name,
                    "role": presence_removed.role,
                    "left_at": datetime.now(UTC).isoformat(),
                },
            )
            await self.broadcast_to_trip(trip_id, leave_event)

        logger.info(
            "WebSocket disconnected [trip=%s, user=%s, conn=%s, remaining_user_conns=%s]",
            trip_id,
            user_id,
            connection_id,
            not user_left_entirely,
        )

    def get_active_presence(self, trip_id: str) -> list[CollaboratorPresence]:
        """Return list of active collaborator presences in a trip room."""
        return list(self._presences.get(trip_id, {}).values())

    def get_room_connection_count(self, trip_id: str) -> int:
        """Return total active WebSocket connections in a trip room."""
        return len(self._rooms.get(trip_id, {}))

    async def broadcast_to_trip(
        self,
        trip_id: str,
        event: TripRealtimeEvent,
        *,
        exclude_connection_id: str | None = None,
    ) -> None:
        """Send a real-time event to all connected clients in a trip room."""
        sockets: list[tuple[str, WebSocket]] = []
        async with self._lock:
            if trip_id in self._rooms:
                sockets = [
                    (cid, ws)
                    for cid, ws in self._rooms[trip_id].items()
                    if cid != exclude_connection_id
                ]

        if not sockets:
            return

        payload_dict = event.to_dict()
        dead_connections: list[str] = []

        for cid, ws in sockets:
            try:
                await ws.send_json(payload_dict)
            except Exception as exc:
                logger.debug("Broadcast failed on conn %s (marking dead): %s", cid, exc)
                dead_connections.append(cid)

        # Cleanup dead connections
        if dead_connections:
            async with self._lock:
                for dead_cid in dead_connections:
                    if trip_id in self._rooms:
                        self._rooms[trip_id].pop(dead_cid, None)
