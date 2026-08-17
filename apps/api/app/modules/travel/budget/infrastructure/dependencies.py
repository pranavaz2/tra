"""Budget Infrastructure Layer — Dependency Injection Containers."""

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
from app.modules.travel.budget.application.budget_service import BudgetService
from app.modules.travel.budget.application.handlers import (
    AddExpenseHandler,
    CreateBudgetHandler,
    DeleteExpenseHandler,
    GetBudgetHandler,
    GetBudgetSummaryHandler,
    ListExpensesHandler,
    UpdateBudgetHandler,
    UpdateExpenseHandler,
)
from app.modules.travel.budget.domain.repositories.interfaces import (
    ITripBudgetRepository,
)
from app.modules.travel.budget.infrastructure.repositories.budget_repository import (
    SQLAlchemyTripBudgetRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import CurrentTripRepository
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider
from app.shared.infrastructure.clock import Clock, SystemClock

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


def get_budget_event_publisher() -> EventPublisher:
    """Return the cached LoggingEventPublisher singleton."""
    return _build_event_publisher()


@lru_cache(maxsize=1)
def _build_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_budget_uuid_provider() -> UUIDProvider:
    """Return the cached StandardUUIDProvider singleton."""
    return _build_uuid_provider()


@lru_cache(maxsize=1)
def _build_clock() -> SystemClock:
    return SystemClock()


def get_budget_clock() -> Clock:
    """Return the cached SystemClock singleton."""
    return _build_clock()


CurrentBudgetEventPublisher = Annotated[
    EventPublisher, Depends(get_budget_event_publisher)
]
CurrentBudgetUUIDProvider = Annotated[
    UUIDProvider, Depends(get_budget_uuid_provider)
]
CurrentBudgetClock = Annotated[
    Clock, Depends(get_budget_clock)
]


# ──────────────────────────────────────────────────────────────────────────── #
# Per-request dependencies (session-bound)                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_budget_repository(db: DatabaseSession) -> ITripBudgetRepository:
    """Build a SQLAlchemyTripBudgetRepository backed by the request-scoped session."""
    return SQLAlchemyTripBudgetRepository(db)


def get_budget_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    """Build a _SessionBoundUnitOfWork that shares the request session."""
    return _SessionBoundUnitOfWork(db)


CurrentBudgetRepository = Annotated[
    ITripBudgetRepository, Depends(get_budget_repository)
]
CurrentBudgetUnitOfWork = Annotated[
    UnitOfWork, Depends(get_budget_unit_of_work)
]


# ──────────────────────────────────────────────────────────────────────────── #
# BudgetService                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


def get_budget_service(
    repository: CurrentBudgetRepository,
    trip_repository: CurrentTripRepository,
    uow: CurrentBudgetUnitOfWork,
    event_publisher: CurrentBudgetEventPublisher,
    uuid_provider: CurrentBudgetUUIDProvider,
    clock: CurrentBudgetClock,
) -> BudgetService:
    """Compose and return a fully-wired BudgetService for this request."""
    return BudgetService(
        repository=repository,
        trip_repository=trip_repository,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=uuid_provider,
        clock=clock,
    )


CurrentBudgetService = Annotated[BudgetService, Depends(get_budget_service)]


# ──────────────────────────────────────────────────────────────────────────── #
# Command/Query Handlers                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


def get_create_budget_handler(service: CurrentBudgetService) -> CreateBudgetHandler:
    return CreateBudgetHandler(service)


def get_update_budget_handler(service: CurrentBudgetService) -> UpdateBudgetHandler:
    return UpdateBudgetHandler(service)


def get_add_expense_handler(service: CurrentBudgetService) -> AddExpenseHandler:
    return AddExpenseHandler(service)


def get_update_expense_handler(service: CurrentBudgetService) -> UpdateExpenseHandler:
    return UpdateExpenseHandler(service)


def get_delete_expense_handler(service: CurrentBudgetService) -> DeleteExpenseHandler:
    return DeleteExpenseHandler(service)


def get_get_budget_handler(service: CurrentBudgetService) -> GetBudgetHandler:
    return GetBudgetHandler(service)


def get_list_expenses_handler(service: CurrentBudgetService) -> ListExpensesHandler:
    return ListExpensesHandler(service)


def get_get_budget_summary_handler(service: CurrentBudgetService) -> GetBudgetSummaryHandler:
    return GetBudgetSummaryHandler(service)


CurrentCreateBudgetHandler = Annotated[
    CreateBudgetHandler, Depends(get_create_budget_handler)
]
CurrentUpdateBudgetHandler = Annotated[
    UpdateBudgetHandler, Depends(get_update_budget_handler)
]
CurrentAddExpenseHandler = Annotated[
    AddExpenseHandler, Depends(get_add_expense_handler)
]
CurrentUpdateExpenseHandler = Annotated[
    UpdateExpenseHandler, Depends(get_update_expense_handler)
]
CurrentDeleteExpenseHandler = Annotated[
    DeleteExpenseHandler, Depends(get_delete_expense_handler)
]
CurrentGetBudgetHandler = Annotated[
    GetBudgetHandler, Depends(get_get_budget_handler)
]
CurrentListExpensesHandler = Annotated[
    ListExpensesHandler, Depends(get_list_expenses_handler)
]
CurrentGetBudgetSummaryHandler = Annotated[
    GetBudgetSummaryHandler, Depends(get_get_budget_summary_handler)
]
