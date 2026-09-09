"""Activity application service."""

from __future__ import annotations

import logging
from typing import Any
import uuid

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.activity.application.dtos import ActivityFeedPageDTO, ActivityLogDTO
from app.modules.travel.activity.domain.entities.activity_log import TripActivityLog
from app.modules.travel.activity.domain.enums import ActivityAction
from app.modules.travel.activity.domain.repositories.interfaces import (
    ITripActivityRepository,
)
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import ForbiddenError, NotFoundError
from app.shared.domain.result import Failure, Result, Success

logger = logging.getLogger(__name__)


class ActivityService:
    """Orchestrates activity feed recording and querying."""

    def __init__(
        self,
        *,
        activity_repository: ITripActivityRepository,
        trip_repository: ITripRepository,
        trip_sharing_repository: ITripCollaborationRepository,
    ) -> None:
        self._activity_repo = activity_repository
        self._trip_repo = trip_repository
        self._sharing_repo = trip_sharing_repository

    async def _verify_access(self, trip_id: TripId, user_id: UserId) -> bool:
        """Verify user has owner/editor/viewer access on trip."""
        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return False

        if trip.owner_id == user_id:
            return True

        collab = await self._sharing_repo.find_by_trip_id(trip_id)
        if collab:
            for member in collab.members:
                if member.user_id == user_id:
                    return True
            if getattr(collab, "is_public", False):
                return True

        if getattr(trip, "privacy", None) and trip.privacy.value == "public":
            return True

        return False

    async def record_activity(
        self,
        *,
        trip_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: ActivityAction,
        entity_type: str,
        entity_id: str,
        title: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an immutable activity log entry (invoked post-commit)."""
        try:
            log_entry = TripActivityLog.create(
                trip_id=trip_id,
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                title=title,
                description=description,
                metadata=metadata or {},
            )
            await self._activity_repo.save(log_entry)
            logger.info(
                "Activity logged [trip=%s, actor=%s, action=%s]",
                trip_id,
                actor_id,
                action.value,
            )
        except Exception as exc:
            logger.warning(
                "Failed to record activity log for trip %s: %s",
                trip_id,
                exc,
            )

    async def get_trip_activities(
        self,
        *,
        trip_id_str: str,
        requester_id_str: str,
        limit: int = 50,
        offset: int = 0,
    ) -> Result[ActivityFeedPageDTO]:
        """Fetch chronological paginated activities for a trip."""
        try:
            trip_uuid = uuid.UUID(trip_id_str)
            user_uuid = uuid.UUID(requester_id_str)
        except ValueError:
            return Failure(NotFoundError("Trip not found"))

        trip_id = TripId(trip_uuid)
        user_id = UserId(user_uuid)

        has_access = await self._verify_access(trip_id, user_id)
        if not has_access:
            return Failure(ForbiddenError("You do not have permission to view activity on this trip"))

        activities = await self._activity_repo.list_by_trip(
            trip_uuid,
            limit=limit,
            offset=offset,
        )
        total_count = await self._activity_repo.count_by_trip(trip_uuid)

        items = [ActivityLogDTO.from_entity(a) for a in activities]
        has_more = (offset + len(items)) < total_count

        return Success(
            ActivityFeedPageDTO(
                items=items,
                total=total_count,
                limit=limit,
                offset=offset,
                has_more=has_more,
            )
        )
