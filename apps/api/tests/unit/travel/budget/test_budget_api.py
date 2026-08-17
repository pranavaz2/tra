"""API endpoint tests for the Budgets router using stub handlers."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.core.security.auth.errors import AuthorizationError
from app.modules.travel.budget.application.dtos import (
    BudgetBreakdownSummary,
    BudgetSummary,
    CategorySummary,
    ExpenseListPage,
    ExpenseSummary,
)
from app.modules.travel.budget.domain.errors import (
    BudgetAlreadyExistsError,
    BudgetNotFoundError,
)
from app.modules.travel.budget.infrastructure.dependencies import (
    get_add_expense_handler,
    get_create_budget_handler,
    get_delete_expense_handler,
    get_get_budget_handler,
    get_get_budget_summary_handler,
    get_list_expenses_handler,
    get_update_budget_handler,
    get_update_expense_handler,
)
from app.modules.travel.budget.presentation.router import router
from app.shared.domain.result import Failure, Success

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants & fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())
BUDGET_ID = str(uuid.uuid4())
CATEGORY_ID = str(uuid.uuid4())
EXPENSE_ID = str(uuid.uuid4())


def _auth_ctx() -> AuthorizationContext:
    now = datetime.now(UTC)
    return AuthorizationContext(
        user_id=USER_ID,
        session_id=str(uuid.uuid4()),
        token_id=str(uuid.uuid4()),
        token_version=1,
        session_version=1,
        authentication_method="password",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        email="test@example.com",
        is_email_verified=True,
    )


def _make_budget_summary() -> BudgetSummary:
    now = datetime.now(UTC)
    return BudgetSummary(
        budget_id=BUDGET_ID,
        trip_id=TRIP_ID,
        owner_id=USER_ID,
        limit=Decimal("2000.00"),
        currency="USD",
        status="active",
        total_spent=Decimal("250.00"),
        remaining=Decimal("1750.00"),
        spent_percentage=Decimal("12.50"),
        categories=[
            CategorySummary(
                category_id=CATEGORY_ID,
                name="Food",
                description="Dining out",
                icon="food",
            )
        ],
        created_at=now,
        updated_at=now,
    )


def _make_expense_summary() -> ExpenseSummary:
    now = datetime.now(UTC)
    return ExpenseSummary(
        expense_id=EXPENSE_ID,
        title="Tasty Lunch",
        amount=Decimal("45.00"),
        currency="USD",
        category_id=CATEGORY_ID,
        expense_type="restaurant",
        expense_date=date(2027, 6, 1),
        description="With friends",
        created_at=now,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub Handlers
# ─────────────────────────────────────────────────────────────────────────────


class _StubHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, message: object) -> object:
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────


async def _auth_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return exc.to_response()


def _make_app(
    *,
    create_result: object | None = None,
    update_result: object | None = None,
    add_expense_result: object | None = None,
    update_expense_result: object | None = None,
    delete_expense_result: object | None = None,
    get_result: object | None = None,
    list_expenses_result: object | None = None,
    get_summary_result: object | None = None,
    authenticated: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AuthorizationError, _auth_error_handler)  # type: ignore[arg-type]
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(router)
    app.include_router(api_v1)

    if authenticated:
        app.dependency_overrides[get_authorization_context] = _auth_ctx

    if create_result is not None:
        app.dependency_overrides[get_create_budget_handler] = lambda: _StubHandler(create_result)
    if update_result is not None:
        app.dependency_overrides[get_update_budget_handler] = lambda: _StubHandler(update_result)
    if add_expense_result is not None:
        app.dependency_overrides[get_add_expense_handler] = lambda: _StubHandler(add_expense_result)
    if update_expense_result is not None:
        app.dependency_overrides[get_update_expense_handler] = (
            lambda: _StubHandler(update_expense_result)
        )
    if delete_expense_result is not None:
        app.dependency_overrides[get_delete_expense_handler] = (
            lambda: _StubHandler(delete_expense_result)
        )
    if get_result is not None:
        app.dependency_overrides[get_get_budget_handler] = lambda: _StubHandler(get_result)
    if list_expenses_result is not None:
        app.dependency_overrides[get_list_expenses_handler] = (
            lambda: _StubHandler(list_expenses_result)
        )
    if get_summary_result is not None:
        app.dependency_overrides[get_get_budget_summary_handler] = (
            lambda: _StubHandler(get_summary_result)
        )

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_budget_returns_201() -> None:
    summary = _make_budget_summary()
    app = _make_app(create_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            f"/api/v1/trips/{TRIP_ID}/budget",
            json={"limit_amount": 2000.00, "currency": "USD"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["budget_id"] == BUDGET_ID
    assert body["data"]["limit"] == "2000.00"


@pytest.mark.asyncio
async def test_create_budget_conflict_returns_409() -> None:
    app = _make_app(create_result=Failure(BudgetAlreadyExistsError(TRIP_ID)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            f"/api/v1/trips/{TRIP_ID}/budget",
            json={"limit_amount": 2000.00, "currency": "USD"},
        )
    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "BUDGET_CONFLICT"


@pytest.mark.asyncio
async def test_get_budget_returns_200() -> None:
    summary = _make_budget_summary()
    app = _make_app(get_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}/budget")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["budget_id"] == BUDGET_ID
    assert body["data"]["limit"] == "2000.00"


@pytest.mark.asyncio
async def test_get_budget_summary_returns_200() -> None:
    summary = _make_budget_summary()
    breakdown = BudgetBreakdownSummary(
        budget=summary,
        category_breakdowns={CATEGORY_ID: Decimal("250.00")},
        type_breakdowns={"restaurant": Decimal("250.00")},
    )
    app = _make_app(get_summary_result=Success(breakdown))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}/budget?summary=true")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["budget"]["budget_id"] == BUDGET_ID
    assert body["data"]["category_breakdowns"][CATEGORY_ID] == "250.00"


@pytest.mark.asyncio
async def test_get_budget_not_found_returns_404() -> None:
    app = _make_app(get_result=Failure(BudgetNotFoundError(TRIP_ID)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}/budget")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "BUDGET_NOT_FOUND"


@pytest.mark.asyncio
async def test_add_expense_returns_201() -> None:
    summary = _make_expense_summary()
    app = _make_app(add_expense_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            f"/api/v1/trips/{TRIP_ID}/budget/expenses",
            json={
                "title": "Tasty Lunch",
                "amount": 45.00,
                "category_id": CATEGORY_ID,
                "expense_type": "restaurant",
                "expense_date": "2027-06-01",
                "description": "With friends",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["expense_id"] == EXPENSE_ID
    assert body["data"]["amount"] == "45.00"


@pytest.mark.asyncio
async def test_list_expenses_returns_200() -> None:
    expense = _make_expense_summary()
    page = ExpenseListPage(
        items=(expense,),
        next_cursor="c1",
        has_more=True,
        limit=20,
    )
    app = _make_app(list_expenses_result=Success(page))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}/budget/expenses?limit=20")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["expense_id"] == EXPENSE_ID
    assert body["data"]["next_cursor"] == "c1"


@pytest.mark.asyncio
async def test_update_expense_returns_200() -> None:
    summary = _make_expense_summary()
    app = _make_app(update_expense_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(
            f"/api/v1/trips/{TRIP_ID}/budget/expenses/{EXPENSE_ID}",
            json={"title": "Tasty Lunch"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["expense_id"] == EXPENSE_ID


@pytest.mark.asyncio
async def test_delete_expense_returns_204() -> None:
    app = _make_app(delete_expense_result=Success(None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.delete(f"/api/v1/trips/{TRIP_ID}/budget/expenses/{EXPENSE_ID}")
    assert resp.status_code == 204
