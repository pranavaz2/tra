"""Itinerary Infrastructure Layer — Dependency Injection Containers."""

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
from app.modules.travel.itinerary.application.handlers import (
    AddItineraryDayHandler,
    AddItineraryItemHandler,
    CreateItineraryHandler,
    GetItineraryHandler,
    RemoveItineraryDayHandler,
    RemoveItineraryItemHandler,
    UpdateItineraryDayHandler,
    UpdateItineraryItemHandler,
)
from app.modules.travel.itinerary.application.itinerary_service import ItineraryService
from app.modules.travel.itinerary.domain.repositories.interfaces import (
    IItineraryRepository,
)
from app.modules.travel.itinerary.infrastructure.repositories.itinerary_repository import (
    SQLAlchemyItineraryRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import CurrentTripRepository
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Session-bound Unit of Work                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class _SessionBoundUnitOfWork:
    """UnitOfWork that wraps an existing request-scoped AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> _SessionBoundUnitOfWork:
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


def get_itinerary_event_publisher() -> EventPublisher:
    """Return the cached LoggingEventPublisher singleton."""
    return _build_event_publisher()


@lru_cache(maxsize=1)
def _build_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_itinerary_uuid_provider() -> UUIDProvider:
    """Return the cached StandardUUIDProvider singleton."""
    return _build_uuid_provider()


CurrentItineraryEventPublisher = Annotated[
    EventPublisher, Depends(get_itinerary_event_publisher)
]
CurrentItineraryUUIDProvider = Annotated[
    UUIDProvider, Depends(get_itinerary_uuid_provider)
]


# ──────────────────────────────────────────────────────────────────────────── #
# Per-request dependencies (session-bound)                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_itinerary_repository(db: DatabaseSession) -> IItineraryRepository:
    """Build a SQLAlchemyItineraryRepository backed by the request-scoped session."""
    return SQLAlchemyItineraryRepository(db)


def get_itinerary_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    """Build a _SessionBoundUnitOfWork that shares the request session."""
    return _SessionBoundUnitOfWork(db)


CurrentItineraryRepository = Annotated[
    IItineraryRepository, Depends(get_itinerary_repository)
]
CurrentItineraryUnitOfWork = Annotated[
    UnitOfWork, Depends(get_itinerary_unit_of_work)
]


# ──────────────────────────────────────────────────────────────────────────── #
# ItineraryService                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


def get_itinerary_service(
    repository: CurrentItineraryRepository,
    trip_repository: CurrentTripRepository,
    uow: CurrentItineraryUnitOfWork,
    event_publisher: CurrentItineraryEventPublisher,
    uuid_provider: CurrentItineraryUUIDProvider,
) -> ItineraryService:
    """Compose and return a fully-wired ItineraryService for this request."""
    return ItineraryService(
        repository=repository,
        trip_repository=trip_repository,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=uuid_provider,
    )


CurrentItineraryService = Annotated[ItineraryService, Depends(get_itinerary_service)]


# ──────────────────────────────────────────────────────────────────────────── #
# Command/Query Handlers                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


def get_create_itinerary_handler(service: CurrentItineraryService) -> CreateItineraryHandler:
    return CreateItineraryHandler(service)


def get_add_itinerary_day_handler(service: CurrentItineraryService) -> AddItineraryDayHandler:
    return AddItineraryDayHandler(service)


def get_update_itinerary_day_handler(
    service: CurrentItineraryService,
) -> UpdateItineraryDayHandler:
    return UpdateItineraryDayHandler(service)


def get_remove_itinerary_day_handler(
    service: CurrentItineraryService,
) -> RemoveItineraryDayHandler:
    return RemoveItineraryDayHandler(service)


def get_add_itinerary_item_handler(service: CurrentItineraryService) -> AddItineraryItemHandler:
    return AddItineraryItemHandler(service)


def get_update_itinerary_item_handler(
    service: CurrentItineraryService,
) -> UpdateItineraryItemHandler:
    return UpdateItineraryItemHandler(service)


def get_remove_itinerary_item_handler(
    service: CurrentItineraryService,
) -> RemoveItineraryItemHandler:
    return RemoveItineraryItemHandler(service)


def get_get_itinerary_handler(service: CurrentItineraryService) -> GetItineraryHandler:
    return GetItineraryHandler(service)


CurrentCreateItineraryHandler = Annotated[
    CreateItineraryHandler, Depends(get_create_itinerary_handler)
]
CurrentAddItineraryDayHandler = Annotated[
    AddItineraryDayHandler, Depends(get_add_itinerary_day_handler)
]
CurrentUpdateItineraryDayHandler = Annotated[
    UpdateItineraryDayHandler, Depends(get_update_itinerary_day_handler)
]
CurrentRemoveItineraryDayHandler = Annotated[
    RemoveItineraryDayHandler, Depends(get_remove_itinerary_day_handler)
]
CurrentAddItineraryItemHandler = Annotated[
    AddItineraryItemHandler, Depends(get_add_itinerary_item_handler)
]
CurrentUpdateItineraryItemHandler = Annotated[
    UpdateItineraryItemHandler, Depends(get_update_itinerary_item_handler)
]
CurrentRemoveItineraryItemHandler = Annotated[
    RemoveItineraryItemHandler, Depends(get_remove_itinerary_item_handler)
]
CurrentGetItineraryHandler = Annotated[
    GetItineraryHandler, Depends(get_get_itinerary_handler)
]
