"""Activity dependency injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.dependencies import DatabaseSession
from app.modules.travel.activity.application.activity_service import ActivityService
from app.modules.travel.activity.domain.repositories.interfaces import (
    ITripActivityRepository,
)
from app.modules.travel.activity.infrastructure.repositories.activity_repository import (
    SQLAlchemyTripActivityRepository,
)
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.sharing.infrastructure.repositories.sharing_repository import (
    SQLAlchemyTripCollaborationRepository,
)
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.infrastructure.repositories.trip_repository import (
    SQLAlchemyTripRepository,
)


def get_activity_repository(
    session: DatabaseSession,
) -> ITripActivityRepository:
    """Return an activity repository instance."""
    return SQLAlchemyTripActivityRepository(session)


def get_activity_service(
    session: DatabaseSession,
) -> ActivityService:
    """Return an ActivityService wired with repositories."""
    activity_repo = SQLAlchemyTripActivityRepository(session)
    trip_repo = SQLAlchemyTripRepository(session)
    sharing_repo = SQLAlchemyTripCollaborationRepository(session)
    return ActivityService(
        activity_repository=activity_repo,
        trip_repository=trip_repo,
        trip_sharing_repository=sharing_repo,
    )


CurrentActivityService = Annotated[ActivityService, Depends(get_activity_service)]
