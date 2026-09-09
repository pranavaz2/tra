"""Unit tests for InMemoryTripConnectionManager and TripRealtimeEvent."""

from __future__ import annotations

import asyncio
import uuid
import pytest

from app.modules.travel.realtime.application.broadcaster import InMemoryTripConnectionManager
from app.modules.travel.realtime.domain.entities.presence import CollaboratorPresence
from app.modules.travel.realtime.domain.enums import EntityActionType, EntityType, RealtimeEventType
from app.modules.travel.realtime.domain.value_objects.realtime_event import TripRealtimeEvent


class FakeWebSocket:
    """Mock WebSocket for unit testing InMemoryTripConnectionManager."""

    def __init__(self) -> None:
        self.sent_messages: list[dict] = []
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self.closed:
            raise RuntimeError("Cannot send on closed websocket")
        self.sent_messages.append(data)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


@pytest.mark.asyncio
async def test_trip_realtime_event_creation():
    """Verify TripRealtimeEvent creates with defaults and serializes cleanly."""
    event = TripRealtimeEvent.create(
        trip_id="trip-123",
        event_type=RealtimeEventType.ITINERARY_ITEM_CREATED,
        entity_type=EntityType.ITEM,
        entity_id="item-456",
        action=EntityActionType.CREATED,
        actor_id="user-789",
        version=2,
        payload={"title": "Visit Eiffel Tower", "cost": 30.0},
    )

    data = event.to_dict()
    assert data["trip_id"] == "trip-123"
    assert data["event_type"] == "itinerary.item_created"
    assert data["entity_type"] == "item"
    assert data["entity_id"] == "item-456"
    assert data["action"] == "created"
    assert data["actor_id"] == "user-789"
    assert data["version"] == 2
    assert data["payload"]["title"] == "Visit Eiffel Tower"
    assert data["timestamp"] is not None
    assert data["event_id"] is not None


@pytest.mark.asyncio
async def test_presence_manager_connect_and_sync():
    """Verify connecting establishes a presence session and broadcasts presence.joined."""
    manager = InMemoryTripConnectionManager()
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()

    # User 1 connects
    conn_id_1 = await manager.connect(
        trip_id="trip-1",
        websocket=ws1,  # type: ignore
        user_id="user-1",
        display_name="Alice",
        role="owner",
    )

    assert len(manager.get_active_presence("trip-1")) == 1
    presence_list_1 = manager.get_active_presence("trip-1")
    assert len(presence_list_1) == 1
    assert presence_list_1[0].user_id == "user-1"
    assert presence_list_1[0].display_name == "Alice"

    # User 2 connects
    conn_id_2 = await manager.connect(
        trip_id="trip-1",
        websocket=ws2,  # type: ignore
        user_id="user-2",
        display_name="Bob",
        role="editor",
    )

    assert len(manager.get_active_presence("trip-1")) == 2

    # ws1 should have received presence.joined for User 2
    joined_events = [m for m in ws1.sent_messages if m.get("event_type") == "presence.joined"]
    assert len(joined_events) == 1
    assert joined_events[0]["payload"]["user_id"] == "user-2"
    assert joined_events[0]["payload"]["display_name"] == "Bob"


@pytest.mark.asyncio
async def test_duplicate_connections_same_user():
    """Verify duplicate connections for same user do not duplicate presence entries."""
    manager = InMemoryTripConnectionManager()
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()

    # Alice opens Tab 1
    conn_id_1 = await manager.connect(
        trip_id="trip-1",
        websocket=ws1,  # type: ignore
        user_id="user-1",
        display_name="Alice",
        role="owner",
    )

    # Alice opens Tab 2
    conn_id_2 = await manager.connect(
        trip_id="trip-1",
        websocket=ws2,  # type: ignore
        user_id="user-1",
        display_name="Alice",
        role="owner",
    )

    # Unique active user count should still be 1
    assert len(manager.get_active_presence("trip-1")) == 1
    assert manager.get_room_connection_count("trip-1") == 2

    # Close Tab 1
    await manager.disconnect(trip_id="trip-1", user_id="user-1", connection_id=conn_id_1)
    # Alice is still connected via Tab 2
    assert len(manager.get_active_presence("trip-1")) == 1

    # Close Tab 2
    await manager.disconnect(trip_id="trip-1", user_id="user-1", connection_id=conn_id_2)
    # Alice is now completely disconnected
    assert len(manager.get_active_presence("trip-1")) == 0


@pytest.mark.asyncio
async def test_room_isolation_between_trips():
    """Verify events broadcast to trip-1 do not leak into trip-2."""
    manager = InMemoryTripConnectionManager()
    ws_trip_1 = FakeWebSocket()
    ws_trip_2 = FakeWebSocket()

    await manager.connect(
        trip_id="trip-1",
        websocket=ws_trip_1,  # type: ignore
        user_id="user-1",
        display_name="Alice",
        role="owner",
    )
    await manager.connect(
        trip_id="trip-2",
        websocket=ws_trip_2,  # type: ignore
        user_id="user-2",
        display_name="Bob",
        role="owner",
    )

    event = TripRealtimeEvent.create(
        trip_id="trip-1",
        event_type=RealtimeEventType.BUDGET_EXPENSE_CREATED,
        entity_type=EntityType.EXPENSE,
        entity_id="exp-1",
        action=EntityActionType.CREATED,
        actor_id="user-1",
        version=1,
    )

    await manager.broadcast_to_trip("trip-1", event)

    # ws_trip_1 received the event
    assert any(m.get("event_type") == "budget.expense_created" for m in ws_trip_1.sent_messages)
    # ws_trip_2 did NOT receive the event
    assert not any(m.get("event_type") == "budget.expense_created" for m in ws_trip_2.sent_messages)


@pytest.mark.asyncio
async def test_exclude_connection_id():
    """Verify exclude_connection_id skips broadcasting to the originator."""
    manager = InMemoryTripConnectionManager()
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()

    conn1 = await manager.connect(
        trip_id="trip-1",
        websocket=ws1,  # type: ignore
        user_id="user-1",
        display_name="Alice",
        role="owner",
    )
    conn2 = await manager.connect(
        trip_id="trip-1",
        websocket=ws2,  # type: ignore
        user_id="user-2",
        display_name="Bob",
        role="editor",
    )

    event = TripRealtimeEvent.create(
        trip_id="trip-1",
        event_type=RealtimeEventType.ITINERARY_DAY_CREATED,
        entity_type=EntityType.DAY,
        entity_id="day-1",
        action=EntityActionType.CREATED,
        actor_id="user-1",
        version=1,
    )

    await manager.broadcast_to_trip("trip-1", event, exclude_connection_id=conn1)

    assert not any(m.get("event_type") == "itinerary.day_created" for m in ws1.sent_messages)
    assert any(m.get("event_type") == "itinerary.day_created" for m in ws2.sent_messages)
