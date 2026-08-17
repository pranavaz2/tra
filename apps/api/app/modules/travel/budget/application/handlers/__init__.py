"""Budget CQRS command and query handlers."""

from __future__ import annotations

import logging

from app.modules.travel.budget.application.budget_service import (
    BudgetService,
)
from app.modules.travel.budget.application.commands import (
    AddExpenseCommand,
    CreateBudgetCommand,
    DeleteExpenseCommand,
    UpdateBudgetCommand,
    UpdateExpenseCommand,
)
from app.modules.travel.budget.application.dtos import (
    AddExpenseResult,
    CreateBudgetResult,
    DeleteExpenseResult,
    GetBudgetResult,
    GetBudgetSummaryResult,
    ListExpensesResult,
    UpdateBudgetResult,
    UpdateExpenseResult,
)
from app.modules.travel.budget.application.queries import (
    GetBudgetQuery,
    GetBudgetSummaryQuery,
    ListExpensesQuery,
)

logger = logging.getLogger(__name__)


class CreateBudgetHandler:
    """CQRS handler for CreateBudgetCommand."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, command: CreateBudgetCommand) -> CreateBudgetResult:
        logger.debug(
            "Handling CreateBudgetCommand",
            extra={"trip_id": command.trip_id, "owner_id": command.requester_id},
        )
        return await self._service.create_budget(command)


class UpdateBudgetHandler:
    """CQRS handler for UpdateBudgetCommand."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, command: UpdateBudgetCommand) -> UpdateBudgetResult:
        logger.debug(
            "Handling UpdateBudgetCommand",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )
        return await self._service.update_budget(command)


class AddExpenseHandler:
    """CQRS handler for AddExpenseCommand."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, command: AddExpenseCommand) -> AddExpenseResult:
        logger.debug(
            "Handling AddExpenseCommand",
            extra={"trip_id": command.trip_id, "expense_title": command.title},
        )
        return await self._service.add_expense(command)


class UpdateExpenseHandler:
    """CQRS handler for UpdateExpenseCommand."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, command: UpdateExpenseCommand) -> UpdateExpenseResult:
        logger.debug(
            "Handling UpdateExpenseCommand",
            extra={"trip_id": command.trip_id, "expense_id": command.expense_id},
        )
        return await self._service.update_expense(command)


class DeleteExpenseHandler:
    """CQRS handler for DeleteExpenseCommand."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, command: DeleteExpenseCommand) -> DeleteExpenseResult:
        logger.debug(
            "Handling DeleteExpenseCommand",
            extra={"trip_id": command.trip_id, "expense_id": command.expense_id},
        )
        return await self._service.delete_expense(command)


class GetBudgetHandler:
    """CQRS handler for GetBudgetQuery."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, query: GetBudgetQuery) -> GetBudgetResult:
        logger.debug(
            "Handling GetBudgetQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.get_budget(query)


class ListExpensesHandler:
    """CQRS handler for ListExpensesQuery."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, query: ListExpensesQuery) -> ListExpensesResult:
        logger.debug(
            "Handling ListExpensesQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.list_expenses(query)


class GetBudgetSummaryHandler:
    """CQRS handler for GetBudgetSummaryQuery."""

    def __init__(self, service: BudgetService) -> None:
        self._service = service

    async def handle(self, query: GetBudgetSummaryQuery) -> GetBudgetSummaryResult:
        logger.debug(
            "Handling GetBudgetSummaryQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.get_budget_summary(query)
