"""Real-Time Infrastructure Layer — Dependency Injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from app.dependencies import DatabaseSession
from app.core.security.jwt.dependencies import get_jwt_service
from app.core.security.jwt.interfaces import JWTService
from app.modules.travel.realtime.application.broadcaster import (
    ITripEventBroadcaster,
    InMemoryTripConnectionManager,
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

# Global singleton connection manager
_connection_manager = InMemoryTripConnectionManager()


def get_trip_connection_manager() -> InMemoryTripConnectionManager:
    """Return the singleton trip connection manager."""
    return _connection_manager


def get_trip_event_broadcaster() -> ITripEventBroadcaster:
    """Return the trip event broadcaster implementation."""
    return _connection_manager


def get_trip_read_repository(
    session: DatabaseSession,
) -> ITripRepository:
    """Return the trip repository instance."""
    return SQLAlchemyTripRepository(session)


def get_trip_sharing_repository(
    session: DatabaseSession,
) -> ITripCollaborationRepository:
    """Return the trip sharing repository instance."""
    return SQLAlchemyTripCollaborationRepository(session)


CurrentTripConnectionManager = Annotated[
    InMemoryTripConnectionManager, Depends(get_trip_connection_manager)
]

CurrentTripEventBroadcaster = Annotated[
    ITripEventBroadcaster, Depends(get_trip_event_broadcaster)
]
