"""RFC 7807 Problem Details error responses for the Budget presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.budget.domain.errors import (
    BudgetAlreadyClosedError,
    BudgetAlreadyExistsError,
    BudgetLimitMustBePositiveError,
    BudgetNotFoundError,
    CategoryNotFoundError,
    CurrencyMismatchError,
    DuplicateCategoryNameError,
    ExpenseNotFoundError,
    TotalSpentCannotBeNegativeError,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_BUDGET_ERROR_BASE = "https://errors.travix.ai/budgets"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _budget_problem(
    *,
    slug: str,
    title: str,
    http_status: int,
    detail: str,
    error_code: str,
    trace_id: str,
    instance: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an RFC 7807 Problem Details body for budget-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_BUDGET_ERROR_BASE}/{slug}",
        "title": title,
        "status": http_status,
        "detail": detail,
        "instance": instance,
        "error_code": error_code,
        "trace_id": trace_id,
    }
    if extra:
        body.update(extra)
    return body


def _validation_problem(
    *,
    trace_id: str,
    detail: str,
    instance: str,
    field: str | None = None,
    error_code: str = "BUDGET_VALIDATION_ERROR",
) -> dict[str, Any]:
    """Build an RFC 7807 body for validation errors."""
    body: dict[str, Any] = {
        "type": _VALIDATION_ERROR_TYPE,
        "title": "Validation Error",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": detail,
        "instance": instance,
        "error_code": "VALIDATION_ERROR",
        "trace_id": trace_id,
    }
    if field:
        body["errors"] = [
            {
                "field": field,
                "error_code": error_code,
                "message": detail,
            }
        ]
    return body


def map_budget_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """Map a TravixError to an RFC 7807 JSONResponse."""
    match error:
        case TripNotFoundError():
            body = _budget_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case BudgetNotFoundError():
            body = _budget_problem(
                slug="budget-not-found",
                title="Budget Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="BUDGET_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case ExpenseNotFoundError():
            body = _budget_problem(
                slug="expense-not-found",
                title="Expense Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="EXPENSE_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case CategoryNotFoundError():
            body = _budget_problem(
                slug="category-not-found",
                title="Category Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="CATEGORY_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case BudgetAlreadyExistsError():
            body = _budget_problem(
                slug="budget-conflict",
                title="Budget Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="BUDGET_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case DuplicateCategoryNameError():
            body = _budget_problem(
                slug="category-conflict",
                title="Duplicate Category Name",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="CATEGORY_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case BudgetAlreadyClosedError():
            body = _budget_problem(
                slug="budget-closed",
                title="Budget Closed",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="BUDGET_CLOSED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case CurrencyMismatchError():
            body = _budget_problem(
                slug="currency-mismatch",
                title="Currency Mismatch",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="CURRENCY_MISMATCH",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case TotalSpentCannotBeNegativeError():
            body = _budget_problem(
                slug="negative-spent",
                title="Total Spent Negative",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="TOTAL_SPENT_NEGATIVE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case BudgetLimitMustBePositiveError():
            body = _budget_problem(
                slug="invalid-limit",
                title="Invalid Limit",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="INVALID_LIMIT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case ForbiddenError():
            body = _budget_problem(
                slug="budget-forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=error.message,
                error_code="BUDGET_FORBIDDEN",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_403_FORBIDDEN)

        case ValidationError():
            body = _validation_problem(
                trace_id=trace_id,
                detail=error.message,
                instance=instance,
                field=getattr(error, "field", None),
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case InfrastructureError():
            body = _budget_problem(
                slug="budget-service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The budget service is temporarily unavailable. Please try again later.",
                error_code="BUDGET_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        case _:
            body = _budget_problem(
                slug="budget-internal-error",
                title="Internal Server Error",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred.",
                error_code="BUDGET_INTERNAL_ERROR",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
