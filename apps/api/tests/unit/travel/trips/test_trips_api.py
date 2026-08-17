"""API endpoint tests for the Trips router using stub handlers."""

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
from app.modules.travel.trips.application.dtos import TripListPage, TripSummary
from app.modules.travel.trips.domain.errors import (
    InvalidTripStatusTransitionError,
    TripNotFoundError,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.infrastructure.dependencies import (
    get_create_trip_handler,
    get_delete_trip_handler,
    get_get_trip_handler,
    get_list_trips_handler,
    get_update_trip_handler,
)
from app.modules.travel.trips.presentation.router import router
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.result import Failure, Success

# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())


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


def _make_summary(
    *,
    title: str = "Test Trip",
    status: TripStatus = TripStatus.DRAFT,
    privacy: TripPrivacy = TripPrivacy.PRIVATE,
) -> TripSummary:
    now = datetime.now(UTC)
    from app.modules.identity.authentication.domain.value_objects.user_id import UserId

    return TripSummary(
        trip_id=TripId(value=uuid.UUID(TRIP_ID)),
        owner_id=UserId.from_str(USER_ID),
        title=title,
        status=status,
        privacy=privacy,
        departure_date=None,
        return_date=None,
        is_date_flexible=False,
        version=1,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub handlers
# ─────────────────────────────────────────────────────────────────────────────


class _StubCreateHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, command: object) -> object:
        return self._result


class _StubUpdateHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, command: object) -> object:
        return self._result


class _StubDeleteHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, command: object) -> object:
        return self._result


class _StubGetHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, query: object) -> object:
        return self._result


class _StubListHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, query: object) -> object:
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────


async def _auth_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return exc.to_response()


def _raise_missing_auth() -> AuthorizationContext:
    raise AuthorizationError.missing_token(trace_id="test-trace", instance="/test")


def _make_app(
    *,
    create_result: object | None = None,
    update_result: object | None = None,
    delete_result: object | None = None,
    get_result: object | None = None,
    list_result: object | None = None,
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
        app.dependency_overrides[get_create_trip_handler] = lambda: _StubCreateHandler(
            create_result
        )
    if update_result is not None:
        app.dependency_overrides[get_update_trip_handler] = lambda: _StubUpdateHandler(
            update_result
        )
    if delete_result is not None:
        app.dependency_overrides[get_delete_trip_handler] = lambda: _StubDeleteHandler(
            delete_result
        )
    if get_result is not None:
        app.dependency_overrides[get_get_trip_handler] = lambda: _StubGetHandler(get_result)
    if list_result is not None:
        app.dependency_overrides[get_list_trips_handler] = lambda: _StubListHandler(
            list_result
        )

    return app


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/trips — create
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_trip_returns_201() -> None:
    summary = _make_summary(title="Lisbon Trip")
    app = _make_app(create_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={"title": "Lisbon Trip"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["data"]["title"] == "Lisbon Trip"
    assert body["data"]["status"] == "draft"


@pytest.mark.asyncio
async def test_create_trip_returns_data_envelope() -> None:
    summary = _make_summary()
    app = _make_app(create_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={"title": "Any Trip"})
    assert "data" in resp.json()


@pytest.mark.asyncio
async def test_create_trip_conflict_returns_409() -> None:
    from app.shared.domain.errors import ConflictError

    err = ConflictError("Title already in use.")
    app = _make_app(create_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={"title": "Dupe"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_trip_validation_error_from_handler_returns_422() -> None:
    from app.shared.domain.errors import ValidationError

    err = ValidationError("Title is too short.", field="title", value="x")
    app = _make_app(create_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={"title": "x"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_trip_empty_title_rejected_by_pydantic() -> None:
    # Pydantic min_length=1 rejects before reaching the handler
    summary = _make_summary()
    app = _make_app(create_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={"title": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_trip_missing_title_returns_422() -> None:
    summary = _make_summary()
    app = _make_app(create_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_trip_no_auth_returns_401() -> None:
    app = _make_app(authenticated=False)
    app.dependency_overrides[get_authorization_context] = _raise_missing_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/trips", json={"title": "Trip"})
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/trips — list
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_trips_returns_200() -> None:
    page = TripListPage(items=(), next_cursor=None, has_more=False, limit=20)
    app = _make_app(list_result=Success(page))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/trips")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_trips_returns_data_envelope_with_items() -> None:
    summary = _make_summary(title="Trip A")
    page = TripListPage(items=(summary,), next_cursor=None, has_more=False, limit=20)
    app = _make_app(list_result=Success(page))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/trips")
    body = resp.json()
    assert body["data"]["items"][0]["title"] == "Trip A"
    assert body["data"]["has_more"] is False


@pytest.mark.asyncio
async def test_list_trips_with_next_cursor_in_response() -> None:
    summary = _make_summary()
    page = TripListPage(items=(summary,), next_cursor="cursor-abc", has_more=True, limit=1)
    app = _make_app(list_result=Success(page))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/trips?limit=1")
    body = resp.json()
    assert body["data"]["next_cursor"] == "cursor-abc"
    assert body["data"]["has_more"] is True


@pytest.mark.asyncio
async def test_list_trips_no_auth_returns_401() -> None:
    app = _make_app(authenticated=False)
    app.dependency_overrides[get_authorization_context] = _raise_missing_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/trips")
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/trips/{trip_id} — get
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trip_returns_200() -> None:
    summary = _make_summary(title="Detail Trip")
    app = _make_app(get_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["title"] == "Detail Trip"


@pytest.mark.asyncio
async def test_get_trip_not_found_returns_404() -> None:
    err = TripNotFoundError(TRIP_ID)
    app = _make_app(get_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 404
    assert resp.json()["error_code"] == "TRIP_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_trip_forbidden_returns_403() -> None:
    err = ForbiddenError("Not your trip.")
    app = _make_app(get_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 403
    assert resp.json()["error_code"] == "TRIP_FORBIDDEN"


@pytest.mark.asyncio
async def test_get_trip_no_auth_returns_401() -> None:
    app = _make_app(authenticated=False)
    app.dependency_overrides[get_authorization_context] = _raise_missing_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /api/v1/trips/{trip_id} — update
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_trip_returns_200() -> None:
    summary = _make_summary(title="Updated Title")
    app = _make_app(update_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(
            f"/api/v1/trips/{TRIP_ID}", json={"title": "Updated Title"}
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_update_trip_invalid_transition_returns_422() -> None:
    err = InvalidTripStatusTransitionError(from_status="draft", to_status="completed")
    app = _make_app(update_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(
            f"/api/v1/trips/{TRIP_ID}", json={"new_status": "completed"}
        )
    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "TRIP_INVALID_STATUS_TRANSITION"
    assert body["from_status"] == "draft"
    assert body["to_status"] == "completed"


@pytest.mark.asyncio
async def test_update_trip_not_found_returns_404() -> None:
    err = TripNotFoundError(TRIP_ID)
    app = _make_app(update_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(f"/api/v1/trips/{TRIP_ID}", json={"title": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_trip_forbidden_returns_403() -> None:
    err = ForbiddenError("Not your trip.")
    app = _make_app(update_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(f"/api/v1/trips/{TRIP_ID}", json={"title": "X"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_trip_empty_body_accepted() -> None:
    summary = _make_summary()
    app = _make_app(update_result=Success(summary))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(f"/api/v1/trips/{TRIP_ID}", json={})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_trip_no_auth_returns_401() -> None:
    app = _make_app(authenticated=False)
    app.dependency_overrides[get_authorization_context] = _raise_missing_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.patch(f"/api/v1/trips/{TRIP_ID}", json={"title": "X"})
    assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/trips/{trip_id} — delete
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_trip_returns_204() -> None:
    app = _make_app(delete_result=Success(None))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.delete(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 204
    assert resp.content == b""


@pytest.mark.asyncio
async def test_delete_trip_not_found_returns_404() -> None:
    err = TripNotFoundError(TRIP_ID)
    app = _make_app(delete_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.delete(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_trip_forbidden_returns_403() -> None:
    err = ForbiddenError("Not your trip.")
    app = _make_app(delete_result=Failure(err))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.delete(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_trip_no_auth_returns_401() -> None:
    app = _make_app(authenticated=False)
    app.dependency_overrides[get_authorization_context] = _raise_missing_auth
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.delete(f"/api/v1/trips/{TRIP_ID}")
    assert resp.status_code == 401
