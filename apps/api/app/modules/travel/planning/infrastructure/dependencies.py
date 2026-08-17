"""FastAPI dependency providers for Travel Planning infrastructure."""

from __future__ import annotations

import logging
from functools import lru_cache
from types import TracebackType
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import CurrentClock, DatabaseSession
from app.modules.travel.planning.application.handlers import (
    AcceptProposalHandler,
    GetProposalByTripHandler,
    GetProposalHandler,
    ListProposalsHandler,
    RejectProposalHandler,
    RequestProposalHandler,
)
from app.modules.travel.planning.application.planning_service import PlanningService
from app.modules.travel.planning.domain.repositories.interfaces import (
    ITripProposalRepository,
)
from app.modules.travel.planning.infrastructure.repositories.proposal_repository import (
    SQLAlchemyTripProposalRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import (
    CurrentTripRepository,
    get_trip_event_publisher,
    get_trip_uuid_provider,
)
from app.services.ai.base import PlanningEngine
from app.services.ai.factory import get_planning_engine
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider

logger = logging.getLogger(__name__)


class _SessionBoundUnitOfWork:
    """UnitOfWork wrapping the request-scoped AsyncSession."""

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
# Singletons                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


@lru_cache(maxsize=1)
def _build_planning_engine() -> PlanningEngine:
    return get_planning_engine()


def get_planning_engine_dependency() -> PlanningEngine:
    """Return the configured PlanningEngine instance."""
    return _build_planning_engine()


CurrentPlanningEngine = Annotated[
    PlanningEngine, Depends(get_planning_engine_dependency)
]


# ──────────────────────────────────────────────────────────────────────────── #
# Per-request deps                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


def get_proposal_repository(db: DatabaseSession) -> ITripProposalRepository:
    """Build a SQLAlchemyTripProposalRepository."""
    return SQLAlchemyTripProposalRepository(db)


def get_planning_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    """Build a _SessionBoundUnitOfWork."""
    return _SessionBoundUnitOfWork(db)


CurrentTripProposalRepository = Annotated[
    ITripProposalRepository, Depends(get_proposal_repository)
]
CurrentPlanningUnitOfWork = Annotated[
    UnitOfWork, Depends(get_planning_unit_of_work)
]


def get_planning_service(
    repository: CurrentTripProposalRepository,
    trip_repository: CurrentTripRepository,
    planning_engine: CurrentPlanningEngine,
    uow: CurrentPlanningUnitOfWork,
    event_publisher: Annotated[EventPublisher, Depends(get_trip_event_publisher)],
    uuid_provider: Annotated[UUIDProvider, Depends(get_trip_uuid_provider)],
    clock: CurrentClock,
) -> PlanningService:
    """Compose and return the PlanningService."""
    return PlanningService(
        repository=repository,
        trip_repository=trip_repository,
        planning_engine=planning_engine,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=uuid_provider,
        clock=clock,
    )


CurrentPlanningService = Annotated[PlanningService, Depends(get_planning_service)]


# ──────────────────────────────────────────────────────────────────────────── #
# Handlers                                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_request_proposal_handler(
    service: CurrentPlanningService,
) -> RequestProposalHandler:
    return RequestProposalHandler(service)


def get_accept_proposal_handler(
    service: CurrentPlanningService,
) -> AcceptProposalHandler:
    return AcceptProposalHandler(service)


def get_reject_proposal_handler(
    service: CurrentPlanningService,
) -> RejectProposalHandler:
    return RejectProposalHandler(service)


def get_get_proposal_handler(
    service: CurrentPlanningService,
) -> GetProposalHandler:
    return GetProposalHandler(service)


def get_get_proposal_by_trip_handler(
    service: CurrentPlanningService,
) -> GetProposalByTripHandler:
    return GetProposalByTripHandler(service)


def get_list_proposals_handler(
    service: CurrentPlanningService,
) -> ListProposalsHandler:
    return ListProposalsHandler(service)


CurrentRequestProposalHandler = Annotated[
    RequestProposalHandler, Depends(get_request_proposal_handler)
]
CurrentAcceptProposalHandler = Annotated[
    AcceptProposalHandler, Depends(get_accept_proposal_handler)
]
CurrentRejectProposalHandler = Annotated[
    RejectProposalHandler, Depends(get_reject_proposal_handler)
]
CurrentGetProposalHandler = Annotated[
    GetProposalHandler, Depends(get_get_proposal_handler)
]
CurrentGetProposalByTripHandler = Annotated[
    GetProposalByTripHandler, Depends(get_get_proposal_by_trip_handler)
]
CurrentListProposalsHandler = Annotated[
    ListProposalsHandler, Depends(get_list_proposals_handler)
]
