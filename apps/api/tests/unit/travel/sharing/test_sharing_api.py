"""API endpoint tests for the Sharing router using stub handlers."""

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
from app.modules.travel.sharing.application.dtos import (
    CollaborationSummary,
    InvitationListPage,
    InvitationSummary,
    MemberListPage,
    MemberSummary,
    ShareTokenSummary,
)
from app.modules.travel.sharing.domain.errors import (
    CollaborationAlreadyExistsError,
    CollaborationNotFoundError,
    MemberNotFoundError,
)
from app.modules.travel.sharing.infrastructure.dependencies import (
    get_accept_invitation_handler,
    get_change_member_role_handler,
    get_create_collaboration_handler,
    get_decline_invitation_handler,
    get_disable_public_sharing_handler,
    get_enable_public_sharing_handler,
    get_get_collaboration_handler,
    get_invite_member_handler,
    get_list_invitations_handler,
    get_list_members_handler,
    get_public_trip_handler,
    get_remove_member_handler,
    get_revoke_invitation_handler,
    get_rotate_share_token_handler,
)
from app.modules.travel.sharing.presentation.router import public_router, router
from app.shared.domain.result import Failure, Success

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants & fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())
COLLAB_ID = str(uuid.uuid4())
MEMBER_ID = str(uuid.uuid4())
INVITATION_ID = str(uuid.uuid4())
SHARE_TOKEN = "a" * 64


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


def _make_collab_summary() -> CollaborationSummary:
    now = datetime.now(UTC)
    return CollaborationSummary(
        collaboration_id=COLLAB_ID,
        trip_id=TRIP_ID,
        owner_id=USER_ID,
        member_count=1,
        is_public=False,
        share_token=None,
        created_at=now,
        updated_at=now,
    )


def _make_member_summary() -> MemberSummary:
    now = datetime.now(UTC)
    return MemberSummary(
        member_id=MEMBER_ID,
        user_id=USER_ID,
        role="owner",
        joined_at=now,
    )


def _make_invitation_summary() -> InvitationSummary:
    now = datetime.now(UTC)
    return InvitationSummary(
        invitation_id=INVITATION_ID,
        invitee_email="invitee@example.com",
        role="editor",
        status="pending",
        expires_at=now + timedelta(days=7),
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
    get_result: object | None = None,
    list_members_result: object | None = None,
    invite_result: object | None = None,
    list_invitations_result: object | None = None,
    accept_result: object | None = None,
    decline_result: object | None = None,
    revoke_result: object | None = None,
    change_role_result: object | None = None,
    remove_member_result: object | None = None,
    enable_public_result: object | None = None,
    disable_public_result: object | None = None,
    rotate_token_result: object | None = None,
    get_public_result: object | None = None,
    authenticated: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AuthorizationError, _auth_error_handler)  # type: ignore[arg-type]
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(router)
    api_v1.include_router(public_router)
    app.include_router(api_v1)

    if authenticated:
        app.dependency_overrides[get_authorization_context] = _auth_ctx

    if create_result is not None:
        app.dependency_overrides[get_create_collaboration_handler] = lambda: _StubHandler(create_result)
    if get_result is not None:
        app.dependency_overrides[get_get_collaboration_handler] = lambda: _StubHandler(get_result)
    if list_members_result is not None:
        app.dependency_overrides[get_list_members_handler] = lambda: _StubHandler(list_members_result)
    if invite_result is not None:
        app.dependency_overrides[get_invite_member_handler] = lambda: _StubHandler(invite_result)
    if list_invitations_result is not None:
        app.dependency_overrides[get_list_invitations_handler] = lambda: _StubHandler(list_invitations_result)
    if accept_result is not None:
        app.dependency_overrides[get_accept_invitation_handler] = lambda: _StubHandler(accept_result)
    if decline_result is not None:
        app.dependency_overrides[get_decline_invitation_handler] = lambda: _StubHandler(decline_result)
    if revoke_result is not None:
        app.dependency_overrides[get_revoke_invitation_handler] = lambda: _StubHandler(revoke_result)
    if change_role_result is not None:
        app.dependency_overrides[get_change_member_role_handler] = lambda: _StubHandler(change_role_result)
    if remove_member_result is not None:
        app.dependency_overrides[get_remove_member_handler] = lambda: _StubHandler(remove_member_result)
    if enable_public_result is not None:
        app.dependency_overrides[get_enable_public_sharing_handler] = lambda: _StubHandler(enable_public_result)
    if disable_public_result is not None:
        app.dependency_overrides[get_disable_public_sharing_handler] = lambda: _StubHandler(disable_public_result)
    if rotate_token_result is not None:
        app.dependency_overrides[get_rotate_share_token_handler] = lambda: _StubHandler(rotate_token_result)
    if get_public_result is not None:
        app.dependency_overrides[get_public_trip_handler] = lambda: _StubHandler(get_public_result)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_collaboration_endpoint_success() -> None:
    expected = _make_collab_summary()
    app = _make_app(create_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(f"/api/v1/trips/{TRIP_ID}/collaboration")

    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["collaboration_id"] == COLLAB_ID
    assert json_data["data"]["trip_id"] == TRIP_ID


@pytest.mark.asyncio
async def test_create_collaboration_endpoint_conflict() -> None:
    app = _make_app(
        create_result=Failure(CollaborationAlreadyExistsError(TRIP_ID))
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(f"/api/v1/trips/{TRIP_ID}/collaboration")

    assert response.status_code == 409
    json_data = response.json()
    assert json_data["error_code"] == "COLLABORATION_CONFLICT"


@pytest.mark.asyncio
async def test_get_collaboration_endpoint_success() -> None:
    expected = _make_collab_summary()
    app = _make_app(get_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{TRIP_ID}/collaboration")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["collaboration_id"] == COLLAB_ID


@pytest.mark.asyncio
async def test_get_collaboration_endpoint_not_found() -> None:
    app = _make_app(get_result=Failure(CollaborationNotFoundError(TRIP_ID)))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{TRIP_ID}/collaboration")

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["error_code"] == "COLLABORATION_NOT_FOUND"


@pytest.mark.asyncio
async def test_list_members_endpoint_success() -> None:
    expected = MemberListPage(
        items=(_make_member_summary(),),
        next_cursor=None,
        has_more=False,
        limit=20,
    )
    app = _make_app(list_members_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{TRIP_ID}/collaboration/members")

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]["items"]) == 1
    assert json_data["data"]["items"][0]["member_id"] == MEMBER_ID


@pytest.mark.asyncio
async def test_invite_member_endpoint_success() -> None:
    expected = _make_invitation_summary()
    app = _make_app(invite_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/trips/{TRIP_ID}/collaboration/invitations",
            json={"invitee_email": "invitee@example.com", "role": "editor"},
        )

    assert response.status_code == 201
    json_data = response.json()
    assert json_data["data"]["invitation_id"] == INVITATION_ID


@pytest.mark.asyncio
async def test_list_invitations_endpoint_success() -> None:
    expected = InvitationListPage(
        items=(_make_invitation_summary(),),
        next_cursor=None,
        has_more=False,
        limit=20,
    )
    app = _make_app(list_invitations_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/api/v1/trips/{TRIP_ID}/collaboration/invitations"
        )

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]["items"]) == 1
    assert json_data["data"]["items"][0]["invitation_id"] == INVITATION_ID


@pytest.mark.asyncio
async def test_accept_invitation_endpoint_success() -> None:
    expected = _make_member_summary()
    app = _make_app(accept_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/trips/{TRIP_ID}/collaboration/invitations/{INVITATION_ID}/accept"
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["member_id"] == MEMBER_ID


@pytest.mark.asyncio
async def test_decline_invitation_endpoint_success() -> None:
    app = _make_app(decline_result=Success(None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            f"/api/v1/trips/{TRIP_ID}/collaboration/invitations/{INVITATION_ID}/decline"
        )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_revoke_invitation_endpoint_success() -> None:
    app = _make_app(revoke_result=Success(None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete(
            f"/api/v1/trips/{TRIP_ID}/collaboration/invitations/{INVITATION_ID}"
        )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_member_role_endpoint_success() -> None:
    expected = _make_member_summary()
    app = _make_app(change_role_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/v1/trips/{TRIP_ID}/collaboration/members/{MEMBER_ID}",
            json={"role": "viewer"},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["member_id"] == MEMBER_ID


@pytest.mark.asyncio
async def test_remove_member_endpoint_success() -> None:
    app = _make_app(remove_member_result=Success(None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete(
            f"/api/v1/trips/{TRIP_ID}/collaboration/members/{MEMBER_ID}"
        )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_enable_public_sharing_endpoint_success() -> None:
    expected = ShareTokenSummary(share_token=SHARE_TOKEN, is_public=True)
    app = _make_app(enable_public_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/v1/trips/{TRIP_ID}/collaboration/sharing",
            json={"action": "enable"},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["share_token"] == SHARE_TOKEN
    assert json_data["data"]["is_public"] is True


@pytest.mark.asyncio
async def test_disable_public_sharing_endpoint_success() -> None:
    app = _make_app(disable_public_result=Success(None))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/v1/trips/{TRIP_ID}/collaboration/sharing",
            json={"action": "disable"},
        )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_rotate_share_token_endpoint_success() -> None:
    expected = ShareTokenSummary(share_token=SHARE_TOKEN, is_public=True)
    app = _make_app(rotate_token_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/v1/trips/{TRIP_ID}/collaboration/sharing",
            json={"action": "rotate"},
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["share_token"] == SHARE_TOKEN


@pytest.mark.asyncio
async def test_get_public_trip_endpoint_success() -> None:
    expected = _make_collab_summary()
    app = _make_app(get_public_result=Success(expected), authenticated=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/public/{SHARE_TOKEN}")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["collaboration_id"] == COLLAB_ID
