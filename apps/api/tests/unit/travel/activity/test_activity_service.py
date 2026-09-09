"""Unit tests for ActivityService."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.activity.application.activity_service import ActivityService
from app.modules.travel.activity.domain.entities.activity_log import TripActivityLog
from app.modules.travel.activity.domain.enums import ActivityAction
from app.modules.travel.activity.domain.repositories.interfaces import (
    ITripActivityRepository,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.result import Failure, Success


class FakeActivityRepository(ITripActivityRepository):
    def __init__(self) -> None:
        self.activities: list[TripActivityLog] = []

    async def save(self, activity: TripActivityLog) -> None:
        self.activities.append(activity)

    async def list_by_trip(
        self,
        trip_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TripActivityLog]:
        trip_activities = [a for a in self.activities if a.trip_id == trip_id]
        # Sort newest first (by index / created_at)
        trip_activities.reverse()
        return trip_activities[offset : offset + limit]

    async def count_by_trip(self, trip_id: uuid.UUID) -> int:
        return len([a for a in self.activities if a.trip_id == trip_id])


@pytest.mark.asyncio
async def test_record_activity_and_retrieve():
    """Verify recording an activity log persists and returns in chronological order."""
    repo = FakeActivityRepository()
    trip_repo = MagicMock()
    sharing_repo = MagicMock()

    owner_uuid = uuid.uuid4()
    trip_uuid = uuid.uuid4()

    trip = Trip.create(
        trip_id=TripId(trip_uuid),
        owner_id=UserId(owner_uuid),
        title=TripTitle("Rome Vacation"),
        privacy=TripPrivacy.PRIVATE,
    )
    trip_repo.find_by_id = AsyncMock(return_value=trip)

    service = ActivityService(
        activity_repository=repo,
        trip_repository=trip_repo,
        trip_sharing_repository=sharing_repo,
    )

    # Record 2 activities
    await service.record_activity(
        trip_id=trip_uuid,
        actor_id=owner_uuid,
        action=ActivityAction.DAY_ADDED,
        entity_type="day",
        entity_id="day-1",
        title="Added Day 1",
        description="Arrival in Rome",
        metadata={"day_number": 1},
    )

    await service.record_activity(
        trip_id=trip_uuid,
        actor_id=owner_uuid,
        action=ActivityAction.ITEM_ADDED,
        entity_type="item",
        entity_id="item-1",
        title="Added Colosseum Visit",
        description="Guided tour at 10:00 AM",
        metadata={"cost": 25.0},
    )

    # Retrieve activities as trip owner
    result = await service.get_trip_activities(
        trip_id_str=str(trip_uuid),
        requester_id_str=str(owner_uuid),
        limit=10,
        offset=0,
    )

    assert isinstance(result, Success)
    feed = result.value
    assert feed.total == 2
    assert len(feed.items) == 2
    assert feed.items[0].action == "item_added"
    assert feed.items[1].action == "day_added"
    assert not feed.has_more


@pytest.mark.asyncio
async def test_get_activities_forbidden_for_unauthorized_user():
    """Verify unauthorized user cannot access trip activities."""
    repo = FakeActivityRepository()
    trip_repo = MagicMock()
    sharing_repo = MagicMock()

    owner_uuid = uuid.uuid4()
    unauthorized_uuid = uuid.uuid4()
    trip_uuid = uuid.uuid4()

    trip = Trip.create(
        trip_id=TripId(trip_uuid),
        owner_id=UserId(owner_uuid),
        title=TripTitle("Private Trip"),
        privacy=TripPrivacy.PRIVATE,
    )
    trip_repo.find_by_id = AsyncMock(return_value=trip)
    sharing_repo.find_by_trip_id = AsyncMock(return_value=None)

    service = ActivityService(
        activity_repository=repo,
        trip_repository=trip_repo,
        trip_sharing_repository=sharing_repo,
    )

    result = await service.get_trip_activities(
        trip_id_str=str(trip_uuid),
        requester_id_str=str(unauthorized_uuid),
    )

    assert isinstance(result, Failure)
