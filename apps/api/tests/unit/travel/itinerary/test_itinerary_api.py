"""API endpoint tests for the Itineraries router using stub handlers."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.core.security.auth.errors import AuthorizationError
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.itinerary.application.dtos import (
    ItinerarySummary,
    ItineraryDaySummary,
    ItineraryItemSummary,
)
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.errors import (
    ItineraryNotFoundError,
    ItineraryDayNotFoundError,
    ItineraryItemNotFoundError,
)
from app.modules.travel.itinerary.infrastructure.dependencies import (
    get_create_itinerary_handler,
    get_add_itinerary_day_handler,
    get_update_itinerary_day_handler,
    get_remove_itinerary_day_handler,
    get_add_itinerary_item_handler,
    get_update_itinerary_item_handler,
    get_remove_itinerary_item_handler,
    get_get_itinerary_handler,
)
from app.modules.travel.itinerary.presentation.router import router
from app.shared.domain.result import Failure, Success

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())
ITINERARY_ID = str(uuid.uuid4())


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


def _make_itinerary_summary() -> ItinerarySummary:
    now = datetime.now(UTC)
    return ItinerarySummary(
        itinerary_id=uuid.UUID(ITINERARY_ID),
        trip_id=uuid.UUID(TRIP_ID),
        version=1,
        days=[
            ItineraryDaySummary(
                day_id=uuid.uuid4(),
                day_number=1,
                title="First Day",
                date=date(2027, 6, 1),
                items=[
                    ItineraryItemSummary(
                        item_id=uuid.uuid4(),
                        day_id=uuid.uuid4(),
                        title="Lunch at London Pub",
                        item_type=ItineraryItemType.RESTAURANT,
                        description="Traditional fish & chips",
                        start_time=None,
                        end_time=None,
                        location_id=None,
                        cost=None,
                        currency=None,
                        created_at=now,
                        updated_at=now,
                    )
                ],
                created_at=now,
                updated_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
        deleted_at=None,
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
    add_day_result: object | None = None,
    update_day_result: object | None = None,
    remove_day_result: object | None = None,
    add_item_result: object | None = None,
    update_item_result: object | None = None,
    remove_item_result: object | None = None,
    get_result: object | None = None,
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
        app.dependency_overrides[get_create_itinerary_handler] = lambda: _StubHandler(create_result)
    if add_day_result is not None:
        app.dependency_overrides[get_add_itinerary_day_handler] = lambda: _StubHandler(add_day_result)
    if update_day_result is not None:
        app.dependency_overrides[get_update_itinerary_day_handler] = lambda: _StubHandler(update_day_result)
    if remove_day_result is not None:
        app.dependency_overrides[get_remove_itinerary_day_handler] = lambda: _StubHandler(remove_day_result)
    if add_item_result is not None:
        app.dependency_overrides[get_add_itinerary_item_handler] = lambda: _StubHandler(add_item_result)
    if update_item_result is not None:
        app.dependency_overrides[get_update_itinerary_item_handler] = lambda: _StubHandler(update_item_result)
    if remove_item_result is not None:
        app.dependency_overrides[get_remove_itinerary_item_handler] = lambda: _StubHandler(remove_item_result)
    if get_result is not None:
        app.dependency_overrides[get_get_itinerary_handler] = lambda: _StubHandler(get_result)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_itinerary_returns_200() -> None:
    summary = _make_itinerary_summary()
    app = _make_app(get_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}/itinerary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["itinerary_id"] == ITINERARY_ID
    assert len(body["data"]["days"]) == 1
    assert body["data"]["days"][0]["title"] == "First Day"


@pytest.mark.asyncio
async def test_get_itinerary_not_found_returns_404() -> None:
    app = _make_app(get_result=Failure(ItineraryNotFoundError(TripId(uuid.UUID(TRIP_ID)))))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}/itinerary")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "ITINERARY_NOT_FOUND"


@pytest.mark.asyncio
async def test_add_day_returns_201() -> None:
    summary = _make_itinerary_summary()
    app = _make_app(add_day_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            f"/api/v1/trips/{TRIP_ID}/itinerary/days",
            json={"day_number": 2, "title": "Day 2", "date": "2027-06-02"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["itinerary_id"] == ITINERARY_ID


@pytest.mark.asyncio
async def test_add_item_returns_201() -> None:
    summary = _make_itinerary_summary()
    day_id = str(summary.days[0].day_id)
    app = _make_app(add_item_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            f"/api/v1/trips/{TRIP_ID}/itinerary/items",
            json={
                "day_id": day_id,
                "title": "Visit Museum",
                "item_type": "activity",
                "description": "Pre-booked slots",
                "cost": 12.00,
                "currency": "GBP",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["itinerary_id"] == ITINERARY_ID
