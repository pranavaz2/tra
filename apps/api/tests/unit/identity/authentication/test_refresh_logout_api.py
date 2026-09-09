"""
Unit tests for POST /api/v1/auth/refresh and POST /api/v1/auth/logout.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.middleware.request_id import RequestIDMiddleware
from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.core.security.auth.errors import AuthorizationError
from app.modules.identity.authentication.domain.entities.credential import (
    AuthenticationCredential,
)
from app.modules.identity.authentication.domain.entities.refresh_token_record import (
    RefreshTokenRecord,
)
from app.modules.identity.authentication.domain.errors import (
    RefreshTokenExpiredError,
    RefreshTokenReuseError,
    RefreshTokenRevokedError,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.password_hash import (
    PasswordHash,
)
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_id import (
    RefreshTokenId,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.dependencies import (
    get_auth_repository,
    get_jwt_service,
    get_refresh_token_service,
    get_refresh_token_store,
    get_session_repository,
)
from app.modules.identity.authentication.presentation.router import router as auth_router
from app.shared.domain.result import Failure, Success

_USER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
_SESSION_ID = uuid.UUID("00000000-0000-4000-8000-000000000002")
_RECORD_ID = uuid.UUID("00000000-0000-4000-8000-000000000003")


async def _auth_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return exc.to_response()


def _make_app(
    mock_token_service: Any,
    mock_token_store: Any,
    mock_auth_repo: Any,
    mock_jwt_service: Any,
    mock_session_repo: Any,
    auth_context: AuthorizationContext | None = None,
) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(AuthorizationError, _auth_error_handler)  # type: ignore[arg-type]

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth_router)
    app.include_router(v1)

    app.dependency_overrides[get_refresh_token_service] = lambda: mock_token_service
    app.dependency_overrides[get_refresh_token_store] = lambda: mock_token_store
    app.dependency_overrides[get_auth_repository] = lambda: mock_auth_repo
    app.dependency_overrides[get_jwt_service] = lambda: mock_jwt_service
    app.dependency_overrides[get_session_repository] = lambda: mock_session_repo

    if auth_context:
        app.dependency_overrides[get_authorization_context] = lambda: auth_context

    return app


@pytest.mark.asyncio
async def test_refresh_success() -> None:
    plain_token = PlainRefreshToken.generate()
    new_plain = PlainRefreshToken.generate()
    record_id = RefreshTokenId(_RECORD_ID)

    mock_service = AsyncMock()
    mock_service.rotate.return_value = Success((new_plain, record_id))

    record = RefreshTokenRecord.create(
        record_id=record_id,
        user_id=UserId(_USER_ID),
        session_id=SessionId(_SESSION_ID),
        token_hash=RefreshTokenHash("0" * 64),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    mock_store = AsyncMock()
    mock_store.find_by_id.return_value = record

    mock_credential = AuthenticationCredential(
        entity_id=UserId(_USER_ID),
        email=Email("user@example.com"),
        password_hash=PasswordHash("$argon2id$v=19$m=65536,t=3,p=4$starthash$endhash"),
        is_active=True,
        is_email_verified=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    mock_auth_repo = AsyncMock()
    mock_auth_repo.find_by_user_id.return_value = mock_credential

    mock_jwt = MagicMock()
    mock_jwt.create_access_token.return_value = "new.jwt.token"

    mock_session_repo = AsyncMock()

    app = _make_app(
        mock_service, mock_store, mock_auth_repo, mock_jwt, mock_session_repo
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": plain_token.as_client_token()},
        )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["access_token"] == "new.jwt.token"
    assert data["refresh_token"] == new_plain.as_client_token()
    assert data["user"]["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_refresh_expired_token() -> None:
    mock_service = AsyncMock()
    mock_service.rotate.return_value = Failure(
        RefreshTokenExpiredError("Token has expired.")
    )

    app = _make_app(
        mock_service, AsyncMock(), AsyncMock(), MagicMock(), AsyncMock()
    )

    plain = PlainRefreshToken.generate()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": plain.as_client_token()},
        )

    assert resp.status_code == 401
    err = resp.json()
    assert err["error_code"] == "AUTH_REFRESH_TOKEN_EXPIRED"


@pytest.mark.asyncio
async def test_refresh_reuse_detection() -> None:
    mock_service = AsyncMock()
    mock_service.rotate.return_value = Failure(
        RefreshTokenReuseError("Token reuse detected.")
    )

    app = _make_app(
        mock_service, AsyncMock(), AsyncMock(), MagicMock(), AsyncMock()
    )

    plain = PlainRefreshToken.generate()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": plain.as_client_token()},
        )

    assert resp.status_code == 401
    err = resp.json()
    assert err["error_code"] == "AUTH_REFRESH_REUSED"


@pytest.mark.asyncio
async def test_logout_success() -> None:
    mock_service = AsyncMock()
    mock_service.revoke.return_value = Success(None)
    mock_service.revoke_all_for_session.return_value = Success(None)

    mock_session_repo = AsyncMock()
    mock_session_repo.delete.return_value = None

    auth_context = AuthorizationContext(
        user_id=str(_USER_ID),
        session_id=str(_SESSION_ID),
        token_id=str(uuid.uuid4()),
        token_version=1,
        session_version=1,
        authentication_method="password",
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        email="user@example.com",
        is_email_verified=True,
    )

    app = _make_app(
        mock_service,
        AsyncMock(),
        AsyncMock(),
        MagicMock(),
        mock_session_repo,
        auth_context=auth_context,
    )

    plain = PlainRefreshToken.generate()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": plain.as_client_token()},
        )

    assert resp.status_code == 204
    mock_service.revoke.assert_awaited_once()
    mock_service.revoke_all_for_session.assert_awaited_once()
    mock_session_repo.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_unauthenticated() -> None:
    app = _make_app(
        AsyncMock(), AsyncMock(), AsyncMock(), MagicMock(), AsyncMock()
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.post(
            "/api/v1/auth/logout",
            json={},
        )

    assert resp.status_code == 401
