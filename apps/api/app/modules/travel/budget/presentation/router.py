"""Budget Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse, Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.budget.application.commands import (
    AddExpenseCommand,
    CreateBudgetCommand,
    DeleteExpenseCommand,
    UpdateBudgetCommand,
    UpdateExpenseCommand,
)
from app.modules.travel.budget.application.queries import (
    GetBudgetQuery,
    GetBudgetSummaryQuery,
    ListExpensesQuery,
)
from app.modules.travel.budget.infrastructure.dependencies import (
    CurrentAddExpenseHandler,
    CurrentCreateBudgetHandler,
    CurrentDeleteExpenseHandler,
    CurrentGetBudgetHandler,
    CurrentGetBudgetSummaryHandler,
    CurrentListExpensesHandler,
    CurrentUpdateBudgetHandler,
    CurrentUpdateExpenseHandler,
)
from app.modules.travel.budget.presentation.error_responses import map_budget_failure
from app.modules.travel.budget.presentation.schemas import (
    BudgetCreateRequest,
    BudgetResponse,
    BudgetSummaryResponse,
    BudgetUpdateRequest,
    DataEnvelope,
    ExpenseCreateRequest,
    ExpenseListResponse,
    ExpenseResponse,
    ExpenseUpdateRequest,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Budgets"])


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/budget — Create budget                                  #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/budget",
    response_model=DataEnvelope[BudgetResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create trip budget",
    operation_id="createBudget",
)
async def create_budget(
    trip_id: str,
    body: BudgetCreateRequest,
    auth: RequireAuthentication,
    handler: CurrentCreateBudgetHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget"

    command = CreateBudgetCommand(
        trip_id=trip_id,
        limit_amount=body.limit_amount,
        currency=body.currency,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=BudgetResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/budget — Get budget details or summary breakdown          #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/budget",
    response_model=DataEnvelope[BudgetResponse | BudgetSummaryResponse],
    summary="Get trip budget",
    operation_id="getBudget",
)
async def get_budget(
    trip_id: str,
    auth: RequireAuthentication,
    get_handler: CurrentGetBudgetHandler,
    summary_handler: CurrentGetBudgetSummaryHandler,
    summary: bool = Query(False, description="If true, return spent breakdown by category & type."),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget"

    if summary:
        query_summary = GetBudgetSummaryQuery(trip_id=trip_id, requester_id=str(auth.user_id))
        result_summary = await summary_handler.handle(query_summary)
        match result_summary:
            case Failure(error=err):
                return map_budget_failure(err, trace_id=trace_id, instance=instance)
            case Success(value=breakdown):
                envelope_summary = DataEnvelope(
                    data=BudgetSummaryResponse.model_validate(breakdown)
                )
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=envelope_summary.model_dump(mode="json", by_alias=True),
                    headers={"X-Request-ID": trace_id},
                )

    query = GetBudgetQuery(trip_id=trip_id, requester_id=str(auth.user_id))
    result = await get_handler.handle(query)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary_val):
            envelope = DataEnvelope(data=BudgetResponse.model_validate(summary_val))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/budget — Update budget                                  #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/budget",
    response_model=DataEnvelope[BudgetResponse],
    summary="Update budget limit or status",
    operation_id="updateBudget",
)
async def update_budget(
    trip_id: str,
    body: BudgetUpdateRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdateBudgetHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget"

    command = UpdateBudgetCommand(
        trip_id=trip_id,
        limit_amount=body.limit_amount,
        status=body.status,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=BudgetResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/budget/expenses — Add an expense                         #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/budget/expenses",
    response_model=DataEnvelope[ExpenseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add expense to budget",
    operation_id="addExpense",
)
async def add_expense(
    trip_id: str,
    body: ExpenseCreateRequest,
    auth: RequireAuthentication,
    handler: CurrentAddExpenseHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget/expenses"

    command = AddExpenseCommand(
        trip_id=trip_id,
        title=body.title,
        amount=body.amount,
        category_id=body.category_id,
        expense_type=body.expense_type,
        expense_date=body.expense_date,
        description=body.description,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ExpenseResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/budget/expenses — List paginated expenses                 #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/budget/expenses",
    response_model=DataEnvelope[ExpenseListResponse],
    summary="List budget expenses",
    operation_id="listExpenses",
)
async def list_expenses(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentListExpensesHandler,
    category_id: str | None = Query(None, description="Filter by category UUID."),
    limit: int = Query(20, ge=1, le=100, description="Page limit."),
    cursor: str | None = Query(None, description="Keyset pagination cursor."),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget/expenses"

    query = ListExpensesQuery(
        trip_id=trip_id,
        category_id=category_id,
        limit=limit,
        cursor=cursor,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=page):
            envelope = DataEnvelope(data=ExpenseListResponse.model_validate(page))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/budget/expenses/{expense_id} — Update an expense        #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/budget/expenses/{expense_id}",
    response_model=DataEnvelope[ExpenseResponse],
    summary="Update expense details",
    operation_id="updateExpense",
)
async def update_expense(
    trip_id: str,
    expense_id: str,
    body: ExpenseUpdateRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdateExpenseHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget/expenses/{expense_id}"

    command = UpdateExpenseCommand(
        trip_id=trip_id,
        expense_id=expense_id,
        title=body.title,
        amount=body.amount,
        category_id=body.category_id,
        expense_type=body.expense_type,
        expense_date=body.expense_date,
        description=body.description,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ExpenseResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id}/budget/expenses/{expense_id} — Delete an expense       #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}/budget/expenses/{expense_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove expense from budget",
    operation_id="deleteExpense",
)
async def delete_expense(
    trip_id: str,
    expense_id: str,
    auth: RequireAuthentication,
    handler: CurrentDeleteExpenseHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/budget/expenses/{expense_id}"

    command = DeleteExpenseCommand(
        trip_id=trip_id,
        expense_id=expense_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_budget_failure(err, trace_id=trace_id, instance=instance)
        case Success():
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"X-Request-ID": trace_id},
            )
