"""BudgetService implementation."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from decimal import Decimal

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.application.commands import (
    AddExpenseCommand,
    CreateBudgetCommand,
    DeleteExpenseCommand,
    UpdateBudgetCommand,
    UpdateExpenseCommand,
)
from app.modules.travel.budget.application.dtos import (
    AddExpenseResult,
    BudgetBreakdownSummary,
    BudgetSummary,
    CreateBudgetResult,
    DeleteExpenseResult,
    ExpenseListPage,
    ExpenseSummary,
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
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.budget_status import BudgetStatus
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.errors import (
    BudgetAlreadyExistsError,
    BudgetNotFoundError,
    ExpenseNotFoundError,
)
from app.modules.travel.budget.domain.repositories.interfaces import (
    ITripBudgetRepository,
)
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider
from app.shared.infrastructure.clock import Clock

logger = logging.getLogger(__name__)


class BudgetService:
    """Orchestrates all use cases for TripBudget and Expenses."""

    def __init__(
        self,
        *,
        repository: ITripBudgetRepository,
        trip_repository: ITripRepository,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._trip_repository = trip_repository
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid_provider = uuid_provider
        self._clock = clock

    async def create_budget(self, command: CreateBudgetCommand) -> CreateBudgetResult:
        """Create a new budget for a trip."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            limit_money = Money(
                amount=command.limit_amount,
                currency=CurrencyCode(command.currency),
            )
        except TravixError as exc:
            return Failure(exc)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        # Load trip & authorize
        try:
            trip = await self._trip_repository.find_by_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load trip.", cause=exc))

        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))
        if trip.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this trip."))

        # Check existing budget
        try:
            exists = await self._repository.exists_for_trip(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Database check failed.", cause=exc))

        if exists:
            return Failure(BudgetAlreadyExistsError(str(trip_id)))

        budget_id = BudgetId(value=self._uuid_provider.generate())
        budget = TripBudget.create(
            budget_id=budget_id,
            trip_id=trip_id,
            owner_id=requester_id,
            limit=limit_money,
        )

        try:
            async with self._uow:
                await self._repository.save(budget)
                await self._uow.commit()
        except Exception as exc:
            logger.error("Failed to save budget", extra={"reason": str(exc)})
            return Failure(InfrastructureError("Failed to save budget.", cause=exc))

        await self._publish(budget.pop_events(), context="create_budget")
        return Success(BudgetSummary.from_aggregate(budget))

    async def update_budget(self, command: UpdateBudgetCommand) -> UpdateBudgetResult:
        """Update a budget's limit or status."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                budget = await self._repository.find_by_trip_id(trip_id)
                if budget is None or budget.is_deleted:
                    return Failure(BudgetNotFoundError(str(trip_id)))
                if budget.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this budget."))

                if command.limit_amount is not None:
                    new_limit = Money(
                        amount=command.limit_amount,
                        currency=budget.limit.currency,
                    )
                    budget.update_limit(new_limit)

                if command.status is not None:
                    try:
                        status_enum = BudgetStatus(command.status)
                    except ValueError:
                        return Failure(
                            ValidationError(
                                f"Invalid status: '{command.status}'.",
                                field="status",
                                value=command.status,
                            )
                        )
                    if status_enum == BudgetStatus.CLOSED:
                        budget.close()
                    elif status_enum == BudgetStatus.ACTIVE:
                        budget.reopen()

                await self._repository.save(budget)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to update budget.", cause=exc))

        await self._publish(budget.pop_events(), context="update_budget")
        return Success(BudgetSummary.from_aggregate(budget))

    async def add_expense(self, command: AddExpenseCommand) -> AddExpenseResult:
        """Add a new expense to a trip budget."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            category_id = CategoryId.from_str(command.category_id)
            expense_type = ExpenseType(command.expense_type)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        expense_id = ExpenseId(value=self._uuid_provider.generate())

        try:
            async with self._uow:
                budget = await self._repository.find_by_trip_id(trip_id)
                if budget is None or budget.is_deleted:
                    return Failure(BudgetNotFoundError(str(trip_id)))
                if budget.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this budget."))

                money = Money(
                    amount=command.amount,
                    currency=budget.limit.currency,
                )
                expense = Expense(
                    entity_id=expense_id,
                    title=command.title,
                    amount=money,
                    category_id=category_id,
                    expense_type=expense_type,
                    description=command.description,
                    expense_date=command.expense_date,
                )

                budget.add_expense(expense)
                await self._repository.save(budget)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to add expense.", cause=exc))

        await self._publish(budget.pop_events(), context="add_expense")
        return Success(ExpenseSummary.from_entity(expense))

    async def update_expense(self, command: UpdateExpenseCommand) -> UpdateExpenseResult:
        """Update an existing expense."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            expense_id = ExpenseId.from_str(command.expense_id)
            category_id = (
                CategoryId.from_str(command.category_id)
                if command.category_id is not None
                else None
            )
            expense_type = (
                ExpenseType(command.expense_type)
                if command.expense_type is not None
                else None
            )
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                budget = await self._repository.find_by_trip_id(trip_id)
                if budget is None or budget.is_deleted:
                    return Failure(BudgetNotFoundError(str(trip_id)))
                if budget.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this budget."))

                expense = next((e for e in budget.expenses if e.entity_id == expense_id), None)
                if expense is None:
                    return Failure(ExpenseNotFoundError(str(expense_id)))

                amount_money = (
                    Money(amount=command.amount, currency=budget.limit.currency)
                    if command.amount is not None
                    else None
                )

                budget.update_expense(
                    expense_id,
                    title=command.title,
                    amount=amount_money,
                    category_id=category_id,
                    expense_type=expense_type,
                    description=command.description,
                    expense_date=command.expense_date,
                )

                await self._repository.save(budget)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to update expense.", cause=exc))

        await self._publish(budget.pop_events(), context="update_expense")
        return Success(ExpenseSummary.from_entity(expense))

    async def delete_expense(self, command: DeleteExpenseCommand) -> DeleteExpenseResult:
        """Delete an expense."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            expense_id = ExpenseId.from_str(command.expense_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                budget = await self._repository.find_by_trip_id(trip_id)
                if budget is None or budget.is_deleted:
                    return Failure(BudgetNotFoundError(str(trip_id)))
                if budget.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this budget."))

                budget.delete_expense(expense_id)
                await self._repository.save(budget)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to delete expense.", cause=exc))

        await self._publish(budget.pop_events(), context="delete_expense")
        return Success(None)

    async def get_budget(self, query: GetBudgetQuery) -> GetBudgetResult:
        """Get the budget details."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            budget = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load budget.", cause=exc))

        if budget is None or budget.is_deleted:
            return Failure(BudgetNotFoundError(str(trip_id)))
        if budget.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this budget."))

        return Success(BudgetSummary.from_aggregate(budget))

    async def list_expenses(self, query: ListExpensesQuery) -> ListExpensesResult:
        """List expenses for a budget with cursor-based pagination."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
            category_id = (
                CategoryId.from_str(query.category_id)
                if query.category_id is not None
                else None
            )
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            budget = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load budget.", cause=exc))

        if budget is None or budget.is_deleted:
            return Failure(BudgetNotFoundError(str(trip_id)))
        if budget.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this budget."))

        # Pagination filtering in-memory
        expenses = list(budget.expenses)
        if category_id is not None:
            expenses = [e for e in expenses if e.category_id == category_id]

        # Keyset sorting: newest first (expense_date desc, created_at desc, expense_id desc)
        expenses.sort(
            key=lambda e: (e.expense_date, e.created_at, str(e.entity_id)),
            reverse=True,
        )

        after_id: ExpenseId | None = None
        if query.cursor is not None:
            try:
                after_id = ExpenseId.from_str(decode_cursor(query.cursor))
            except Exception:
                return Failure(
                    ValidationError(
                        "Invalid pagination cursor.",
                        field="cursor",
                        value=query.cursor,
                    )
                )

        if after_id is not None:
            cursor_exp = next((e for e in expenses if e.entity_id == after_id), None)
            if cursor_exp is not None:
                def _after(e: Expense) -> bool:
                    if e.expense_date < cursor_exp.expense_date:
                        return True
                    if e.expense_date == cursor_exp.expense_date:
                        if e.created_at < cursor_exp.created_at:
                            return True
                        if e.created_at == cursor_exp.created_at:
                            return str(e.entity_id) < str(cursor_exp.entity_id)
                    return False
                expenses = [e for e in expenses if _after(e)]

        query.limit + 1
        has_more = len(expenses) > query.limit
        if has_more:
            expenses = expenses[:query.limit]

        next_cursor: str | None = None
        if has_more and expenses:
            next_cursor = encode_cursor(str(expenses[-1].entity_id))

        return Success(
            ExpenseListPage(
                items=tuple(ExpenseSummary.from_entity(e) for e in expenses),
                next_cursor=next_cursor,
                has_more=has_more,
                limit=query.limit,
            )
        )

    async def get_budget_summary(self, query: GetBudgetSummaryQuery) -> GetBudgetSummaryResult:
        """Get the budget summary and breakdowns by category & type."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            budget = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load budget.", cause=exc))

        if budget is None or budget.is_deleted:
            return Failure(BudgetNotFoundError(str(trip_id)))
        if budget.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this budget."))

        # Breakdown calculations
        category_breakdowns = {str(c.entity_id): Decimal("0.00") for c in budget.categories}
        type_breakdowns = {t.value: Decimal("0.00") for t in ExpenseType}

        for exp in budget.expenses:
            cat_str = str(exp.category_id)
            if cat_str in category_breakdowns:
                category_breakdowns[cat_str] += exp.amount.amount
            else:
                category_breakdowns[cat_str] = exp.amount.amount

            type_val = exp.expense_type.value
            type_breakdowns[type_val] += exp.amount.amount

        # Filter out categories and types with 0 spend to be clean
        category_breakdowns = {k: v for k, v in category_breakdowns.items() if v > 0}
        type_breakdowns = {k: v for k, v in type_breakdowns.items() if v > 0}

        return Success(
            BudgetBreakdownSummary(
                budget=BudgetSummary.from_aggregate(budget),
                category_breakdowns=category_breakdowns,
                type_breakdowns=type_breakdowns,
            )
        )

    async def _publish(self, events: Sequence[DomainEvent], *, context: str) -> None:
        """Publish domain events safely."""
        if not events:
            return
        try:
            await self._event_publisher.publish(events)
        except Exception as exc:
            logger.error(
                "Event publication failed",
                extra={
                    "context": context,
                    "event_count": len(events),
                    "reason": str(exc),
                },
            )
