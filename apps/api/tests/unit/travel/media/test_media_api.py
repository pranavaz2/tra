"""API endpoint tests for the Trip Media router using stub handlers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.core.security.auth.errors import AuthorizationError
from app.modules.travel.media.application.dtos import (
    MediaItemSummary,
    MediaListPage,
)
from app.modules.travel.media.domain.errors import (
    MediaCollectionNotFoundError,
    MediaItemNotFoundError,
    MimeTypeNotSupportedError,
)
from app.modules.travel.media.infrastructure.dependencies import (
    get_attach_media_to_activity_handler,
    get_attach_media_to_expense_handler,
    get_delete_media_handler,
    get_get_media_handler,
    get_list_media_handler,
    get_update_caption_handler,
    get_upload_media_handler,
)
from app.modules.travel.media.presentation.router import router
from app.shared.domain.result import Failure, Success

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants & fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())
COLL_ID = str(uuid.uuid4())
MEDIA_ID = str(uuid.uuid4())
ACT_ID = str(uuid.uuid4())
EXP_ID = str(uuid.uuid4())


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


def _make_media_item_summary() -> MediaItemSummary:
    now = datetime.now(UTC)
    return MediaItemSummary(
        media_id=MEDIA_ID,
        collection_id=COLL_ID,
        url="https://storage.travix.ai/trips/media/vacation.jpg",
        media_type="photo",
        status="available",
        mime_type="image/jpeg",
        size_bytes=5000,
        file_name="vacation.jpg",
        width=1920,
        height=1080,
        duration_seconds=None,
        caption="Fun day!",
        uploaded_by=USER_ID,
        activity_id=None,
        expense_id=None,
        created_at=now,
        updated_at=now,
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
    upload_result: object | None = None,
    list_result: object | None = None,
    get_result: object | None = None,
    update_result: object | None = None,
    delete_result: object | None = None,
    attach_act_result: object | None = None,
    attach_exp_result: object | None = None,
    authenticated: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AuthorizationError, _auth_error_handler)  # type: ignore[arg-type]
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(router)
    app.include_router(api_v1)

    if authenticated:
        app.dependency_overrides[get_authorization_context] = _auth_ctx

    if upload_result is not None:
        app.dependency_overrides[get_upload_media_handler] = lambda: _StubHandler(upload_result)
    if list_result is not None:
        app.dependency_overrides[get_list_media_handler] = lambda: _StubHandler(list_result)
    if get_result is not None:
        app.dependency_overrides[get_get_media_handler] = lambda: _StubHandler(get_result)
    if update_result is not None:
        app.dependency_overrides[get_update_caption_handler] = lambda: _StubHandler(update_result)
    if delete_result is not None:
        app.dependency_overrides[get_delete_media_handler] = lambda: _StubHandler(delete_result)
    if attach_act_result is not None:
        app.dependency_overrides[get_attach_media_to_activity_handler] = lambda: _StubHandler(attach_act_result)
    if attach_exp_result is not None:
        app.dependency_overrides[get_attach_media_to_expense_handler] = lambda: _StubHandler(attach_exp_result)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_media_endpoint_success() -> None:
    expected = _make_media_item_summary()
    app = _make_app(upload_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # FastAPI TestClient / HTTPX multipart/form-data upload
        files = {"file": ("vacation.jpg", b"fake_jpeg_content", "image/jpeg")}
        response = await client.post(f"/api/v1/trips/{TRIP_ID}/media", files=files)

    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["media_id"] == MEDIA_ID
    assert json_data["data"]["file_name"] == "vacation.jpg"


@pytest.mark.asyncio
async def test_upload_media_endpoint_mime_unsupported() -> None:
    app = _make_app(
        upload_result=Failure(MimeTypeNotSupportedError("application/x-msdownload", []))
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        files = {"file": ("danger.exe", b"bytes", "application/x-msdownload")}
        response = await client.post(f"/api/v1/trips/{TRIP_ID}/media", files=files)

    assert response.status_code == 422
    json_data = response.json()
    assert json_data["error_code"] == "MIME_TYPE_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_list_media_endpoint_success() -> None:
    expected = MediaListPage(
        items=(_make_media_item_summary(),),
        next_cursor=None,
        has_more=False,
        limit=20,
    )
    app = _make_app(list_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{TRIP_ID}/media")

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]["items"]) == 1
    assert json_data["data"]["items"][0]["media_id"] == MEDIA_ID


@pytest.mark.asyncio
async def test_get_media_item_endpoint_success() -> None:
    expected = _make_media_item_summary()
    app = _make_app(get_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{TRIP_ID}/media/{MEDIA_ID}")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["media_id"] == MEDIA_ID


@pytest.mark.asyncio
async def test_get_media_item_endpoint_not_found() -> None:
    app = _make_app(get_result=Failure(MediaItemNotFoundError(MEDIA_ID)))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{TRIP_ID}/media/{MEDIA_ID}")

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["error_code"] == "MEDIA_ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_media_caption_endpoint_success() -> None:
    expected = _make_media_item_summary()
    app = _make_app(update_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/v1/trips/{TRIP_ID}/media/{MEDIA_ID}",
            json={"caption": "Updated caption!"},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["media_id"] == MEDIA_ID


@pytest.mark.asyncio
async def test_delete_media_item_endpoint_success() -> None:
    app = _make_app(delete_result=Success(None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete(f"/api/v1/trips/{TRIP_ID}/media/{MEDIA_ID}")

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_attach_media_to_activity_endpoint_success() -> None:
    expected = _make_media_item_summary()
    app = _make_app(attach_act_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/trips/{TRIP_ID}/media/{MEDIA_ID}/activity",
            json={"activity_id": ACT_ID},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["media_id"] == MEDIA_ID


@pytest.mark.asyncio
async def test_attach_media_to_expense_endpoint_success() -> None:
    expected = _make_media_item_summary()
    app = _make_app(attach_exp_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/trips/{TRIP_ID}/media/{MEDIA_ID}/expense",
            json={"expense_id": EXP_ID},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["media_id"] == MEDIA_ID
