"""
FastAPI dependency providers — Trips infrastructure.

Wires concrete infrastructure implementations to the TripService and its
CQRS handlers. Consumers import the typed Annotated aliases and declare
them in route function signatures:

    from app.modules.travel.trips.infrastructure.dependencies import (
        CurrentCreateTripHandler,
        CurrentListTripsHandler,
    )

    @router.post("/trips")
    async def create_trip(
        body: TripCreateRequest,
        auth: RequireAuthentication,
        handler: CurrentCreateTripHandler,
    ) -> Response:
        ...

Session sharing:
  TripService requires that the repository and the Unit of Work share the
  same database session (so repository flushes fall inside the UoW commit
  boundary). Both are built from the request-scoped DatabaseSession injected
  by FastAPI. The _SessionBoundUnitOfWork wraps that session without creating
  a new one; the SQLAlchemyTripRepository receives the same session directly.

  The DatabaseSession (get_db_session) auto-commits when the handler returns
  successfully. TripService commits earlier via uow.commit(). The end-of-request
  commit is therefore a no-op (no pending changes). On exception, both the UoW
  and DatabaseSession roll back.

Singleton strategy:
  - LoggingEventPublisher and StandardUUIDProvider are stateless — cached via
    lru_cache and shared across all requests.
  - _SessionBoundUnitOfWork and SQLAlchemyTripRepository are per-request (one
    per DatabaseSession).
  - TripService and handlers are per-request (lightweight; no state outside the
    injected dependencies).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from types import TracebackType
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DatabaseSession
from app.modules.identity.authentication.infrastructure.event_publisher import (
    LoggingEventPublisher,
)
from app.modules.travel.trips.application.handlers import (
    CreateTripHandler,
    DeleteTripHandler,
    GetTripHandler,
    ListTripsHandler,
    UpdateTripHandler,
)
from app.modules.travel.trips.application.trip_service import TripService
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.infrastructure.repositories.trip_repository import (
    SQLAlchemyTripRepository,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Session-bound Unit of Work                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class _SessionBoundUnitOfWork:
    """
    UnitOfWork that wraps an existing request-scoped AsyncSession.

    Shares the session with SQLAlchemyTripRepository so all repository
    flushes fall inside the same transaction boundary as uow.commit().

    __aenter__ is a no-op — the session is already open.
    __aexit__ rolls back when an exception exits the context; is a no-op
    otherwise (TripService commits explicitly before exiting).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> "_SessionBoundUnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self._session.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


# ──────────────────────────────────────────────────────────────────────────── #
# Infrastructure singletons                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


@lru_cache(maxsize=1)
def _build_event_publisher() -> LoggingEventPublisher:
    return LoggingEventPublisher()


def get_trip_event_publisher() -> EventPublisher:
    """Return the cached LoggingEventPublisher singleton."""
    return _build_event_publisher()


@lru_cache(maxsize=1)
def _build_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_trip_uuid_provider() -> UUIDProvider:
    """Return the cached StandardUUIDProvider singleton."""
    return _build_uuid_provider()


CurrentTripEventPublisher = Annotated[EventPublisher, Depends(get_trip_event_publisher)]
CurrentTripUUIDProvider = Annotated[UUIDProvider, Depends(get_trip_uuid_provider)]

# ──────────────────────────────────────────────────────────────────────────── #
# Per-request dependencies (session-bound)                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_trip_repository(db: DatabaseSession) -> ITripRepository:
    """Build a SQLAlchemyTripRepository backed by the request-scoped session."""
    return SQLAlchemyTripRepository(db)


def get_trip_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    """
    Build a _SessionBoundUnitOfWork that shares the request-scoped session.

    Both the repository and this UoW use the same session, ensuring repository
    flushes are included in the same commit boundary.
    """
    return _SessionBoundUnitOfWork(db)


CurrentTripRepository = Annotated[ITripRepository, Depends(get_trip_repository)]
CurrentTripUnitOfWork = Annotated[UnitOfWork, Depends(get_trip_unit_of_work)]

# ──────────────────────────────────────────────────────────────────────────── #
# TripService                                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


def get_trip_service(
    repository: CurrentTripRepository,
    uow: CurrentTripUnitOfWork,
    event_publisher: CurrentTripEventPublisher,
    uuid_provider: CurrentTripUUIDProvider,
) -> TripService:
    """Compose and return a fully-wired TripService for this request."""
    return TripService(
        repository=repository,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=uuid_provider,
    )


CurrentTripService = Annotated[TripService, Depends(get_trip_service)]
"""
Injectable TripService. Override in tests:

    app.dependency_overrides[get_trip_service] = lambda: MockTripService()
"""

# ──────────────────────────────────────────────────────────────────────────── #
# CQRS handler dependencies                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


def get_create_trip_handler(service: CurrentTripService) -> CreateTripHandler:
    """Return a CreateTripHandler backed by the injected TripService."""
    return CreateTripHandler(service)


def get_update_trip_handler(service: CurrentTripService) -> UpdateTripHandler:
    """Return an UpdateTripHandler backed by the injected TripService."""
    return UpdateTripHandler(service)


def get_delete_trip_handler(service: CurrentTripService) -> DeleteTripHandler:
    """Return a DeleteTripHandler backed by the injected TripService."""
    return DeleteTripHandler(service)


def get_get_trip_handler(service: CurrentTripService) -> GetTripHandler:
    """Return a GetTripHandler backed by the injected TripService."""
    return GetTripHandler(service)


def get_list_trips_handler(service: CurrentTripService) -> ListTripsHandler:
    """Return a ListTripsHandler backed by the injected TripService."""
    return ListTripsHandler(service)


CurrentCreateTripHandler = Annotated[CreateTripHandler, Depends(get_create_trip_handler)]
"""Injectable CreateTripHandler. Requires valid DatabaseSession."""

CurrentUpdateTripHandler = Annotated[UpdateTripHandler, Depends(get_update_trip_handler)]
"""Injectable UpdateTripHandler. Requires valid DatabaseSession."""

CurrentDeleteTripHandler = Annotated[DeleteTripHandler, Depends(get_delete_trip_handler)]
"""Injectable DeleteTripHandler. Requires valid DatabaseSession."""

CurrentGetTripHandler = Annotated[GetTripHandler, Depends(get_get_trip_handler)]
"""Injectable GetTripHandler. Requires valid DatabaseSession."""

CurrentListTripsHandler = Annotated[ListTripsHandler, Depends(get_list_trips_handler)]
"""Injectable ListTripsHandler. Requires valid DatabaseSession."""
