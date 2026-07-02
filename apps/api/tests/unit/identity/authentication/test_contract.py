"""
API Contract Tests — frozen schema verification.

These tests verify that the Registration API, Login API, and Problem Details
error responses conform to the frozen API contract. They exist to catch
accidental schema breakage between sprints.

Contract version: TASK-2.12
Covers: POST /api/v1/auth/register, POST /api/v1/auth/login

Rules:
  - All required response fields must be present.
  - Required field types must match the contract.
  - Error responses must be RFC 7807 Problem Details.
  - No tests here test business logic — that lives in test_login_api.py and
    test_registration_api.py. These tests verify shape only.

asyncio_mode = "auto" (pyproject.toml).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.middleware.request_id import RequestIDMiddleware
from app.modules.identity.authentication.application.dtos import (
    AuthenticatedSessionSummary,
    RegistrationSummary,
)
from app.modules.identity.authentication.domain.errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.dependencies import (
    get_login_service,
    get_registration_service,
)
from app.modules.identity.authentication.presentation.router import router as auth_router
from app.shared.domain.result import Failure, Success

# ──────────────────────────────────────────────────────────────────────────── #
# Frozen contract definitions                                                    #
# ──────────────────────────────────────────────────────────────────────────── #

# Required top-level keys in every RFC 7807 error response.
_RFC7807_REQUIRED_KEYS: frozenset[str] = frozenset({
    "type", "title", "status", "detail", "instance", "error_code", "trace_id",
})

# Required keys in a successful login response body (inside "data").
_LOGIN_SUCCESS_CONTRACT: frozenset[str] = frozenset({
    "access_token",
    "refresh_token",
    "token_type",
    "access_token_expires_at",
    "refresh_token_expires_at",
    "session",
    "user",
})

_LOGIN_SESSION_CONTRACT: frozenset[str] = frozenset({
    "session_id",
    "created_at",
})

_LOGIN_USER_CONTRACT: frozenset[str] = frozenset({
    "user_id",
    "email",
    "is_email_verified",
})

# Required keys in a successful registration response body (inside "data").
_REGISTER_SUCCESS_CONTRACT: frozenset[str] = frozenset({
    "user_id",
    "email",
    "requires_verification",
    "message",
})

# ──────────────────────────────────────────────────────────────────────────── #
# Stub services                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #

_NOW = datetime.now(UTC)
_USER_ID = str(uuid.uuid4())
_SESSION_ID = str(uuid.uuid4())
_EMAIL = "contract@example.com"


def _make_login_summary() -> AuthenticatedSessionSummary:
    return AuthenticatedSessionSummary(
        user_id=UserId.from_str(_USER_ID),
        email=Email(_EMAIL),
        session_id=SessionId.from_str(_SESSION_ID),
        access_token="header.payload.sig",
        plain_refresh_token=PlainRefreshToken.generate(),
        access_token_expires_at=_NOW + timedelta(minutes=15),
        refresh_token_expires_at=_NOW + timedelta(days=7),
        is_email_verified=True,
    )


def _make_registration_summary(*, with_session: bool = False) -> RegistrationSummary:
    return RegistrationSummary(
        user_id=UserId.from_str(_USER_ID),
        email=Email(_EMAIL),
        is_email_verified=False,
        session_created=with_session,
        requires_email_verification=True,
    )


class _StubLoginService:
    def __init__(self, *, succeed: bool = True) -> None:
        self._succeed = succeed

    async def execute(self, command: Any) -> Any:
        if self._succeed:
            return Success(_make_login_summary())
        return Failure(InvalidCredentialsError())


class _StubRegistrationService:
    def __init__(self, *, succeed: bool = True) -> None:
        self._succeed = succeed

    async def execute(self, command: Any) -> Any:
        if self._succeed:
            return Success(_make_registration_summary())
        return Failure(EmailAlreadyExistsError(_EMAIL))


# ──────────────────────────────────────────────────────────────────────────── #
# Test app factory                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_app(
    *,
    login_stub: _StubLoginService | None = None,
    registration_stub: _StubRegistrationService | None = None,
) -> FastAPI:
    from app.core.security.auth.errors import AuthorizationError
    from fastapi.responses import JSONResponse

    async def _auth_err_handler(request: Any, exc: AuthorizationError) -> JSONResponse:
        return exc.to_response()

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(AuthorizationError, _auth_err_handler)  # type: ignore[arg-type]

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth_router)
    app.include_router(v1)

    if login_stub is not None:
        app.dependency_overrides[get_login_service] = lambda: login_stub
    if registration_stub is not None:
        app.dependency_overrides[get_registration_service] = lambda: registration_stub

    return app


def _client(
    *,
    login_stub: _StubLoginService | None = None,
    registration_stub: _StubRegistrationService | None = None,
) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(_make_app(login_stub=login_stub, registration_stub=registration_stub)),
        base_url="http://testserver",
    )


# ──────────────────────────────────────────────────────────────────────────── #
# Login contract                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


class TestLoginSuccessContract:
    """Successful login response must contain exactly the contracted fields."""

    async def test_status_200(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        assert r.status_code == 200

    async def test_data_envelope_present(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        assert "data" in r.json()

    async def test_all_required_top_level_fields(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        data = r.json()["data"]
        missing = _LOGIN_SUCCESS_CONTRACT - set(data.keys())
        assert not missing, f"Login response missing fields: {missing}"

    async def test_token_type_is_bearer(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        assert r.json()["data"]["token_type"] == "Bearer"

    async def test_session_object_shape(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        session = r.json()["data"]["session"]
        missing = _LOGIN_SESSION_CONTRACT - set(session.keys())
        assert not missing, f"Session object missing fields: {missing}"

    async def test_user_object_shape(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        user = r.json()["data"]["user"]
        missing = _LOGIN_USER_CONTRACT - set(user.keys())
        assert not missing, f"User object missing fields: {missing}"

    async def test_access_token_is_string(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        assert isinstance(r.json()["data"]["access_token"], str)

    async def test_refresh_token_is_string(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        assert isinstance(r.json()["data"]["refresh_token"], str)

    async def test_expires_at_fields_are_iso_strings(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        data = r.json()["data"]
        # ISO 8601 strings — verify they are parseable
        datetime.fromisoformat(data["access_token_expires_at"])
        datetime.fromisoformat(data["refresh_token_expires_at"])

    async def test_x_request_id_header_present(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=True)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "Secret123!"})
        assert "x-request-id" in r.headers


class TestLoginErrorContract:
    """Login error responses must conform to RFC 7807."""

    async def test_invalid_credentials_401(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=False)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "wrong"})
        assert r.status_code == 401

    async def test_invalid_credentials_rfc7807_shape(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=False)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "wrong"})
        body = r.json()
        missing = _RFC7807_REQUIRED_KEYS - set(body.keys())
        assert not missing, f"Error response missing RFC 7807 fields: {missing}"

    async def test_validation_error_422_rfc7807_shape(self) -> None:
        async with _client(login_stub=_StubLoginService()) as c:
            r = await c.post("/api/v1/auth/login", json={"email": "", "password": "x"})
        assert r.status_code == 422

    async def test_type_field_uses_travix_error_base(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=False)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "wrong"})
        assert r.json()["type"].startswith("https://errors.travix.ai/auth/")

    async def test_status_field_matches_http_status(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=False)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "wrong"})
        assert r.json()["status"] == r.status_code


# ──────────────────────────────────────────────────────────────────────────── #
# Registration contract                                                          #
# ──────────────────────────────────────────────────────────────────────────── #


class TestRegistrationSuccessContract:
    """Successful registration response must contain the contracted fields."""

    async def test_status_201(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=True)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        assert r.status_code == 201

    async def test_data_envelope_present(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=True)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        assert "data" in r.json()

    async def test_all_required_fields_present(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=True)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        data = r.json()["data"]
        missing = _REGISTER_SUCCESS_CONTRACT - set(data.keys())
        assert not missing, f"Registration response missing fields: {missing}"

    async def test_requires_verification_is_bool(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=True)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        assert isinstance(r.json()["data"]["requires_verification"], bool)

    async def test_user_id_is_string(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=True)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        assert isinstance(r.json()["data"]["user_id"], str)


class TestRegistrationErrorContract:
    """Registration error responses must conform to RFC 7807."""

    async def test_conflict_409_on_duplicate(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=False)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        assert r.status_code == 409

    async def test_rfc7807_shape_on_conflict(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=False)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        body = r.json()
        missing = _RFC7807_REQUIRED_KEYS - set(body.keys())
        assert not missing, f"Error response missing RFC 7807 fields: {missing}"

    async def test_status_field_matches_http_status(self) -> None:
        async with _client(registration_stub=_StubRegistrationService(succeed=False)) as c:
            r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )
        assert r.json()["status"] == r.status_code


# ──────────────────────────────────────────────────────────────────────────── #
# Problem Details consistency                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestProblemDetailsConsistency:
    """All error shapes must be consistent across endpoints."""

    async def test_login_and_registration_errors_share_field_names(self) -> None:
        async with _client(
            login_stub=_StubLoginService(succeed=False),
            registration_stub=_StubRegistrationService(succeed=False),
        ) as c:
            login_r = await c.post(
                "/api/v1/auth/login",
                json={"email": _EMAIL, "password": "wrong"},
            )
            reg_r = await c.post(
                "/api/v1/auth/register",
                json={"email": _EMAIL, "password": "Secret123!"},
            )

        login_fields = set(login_r.json().keys())
        reg_fields = set(reg_r.json().keys())
        # Both must contain all required RFC 7807 fields.
        assert _RFC7807_REQUIRED_KEYS.issubset(login_fields)
        assert _RFC7807_REQUIRED_KEYS.issubset(reg_fields)

    async def test_trace_id_is_non_empty_string(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=False)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "x"})
        trace_id = r.json()["trace_id"]
        assert isinstance(trace_id, str) and trace_id

    async def test_instance_field_contains_path(self) -> None:
        async with _client(login_stub=_StubLoginService(succeed=False)) as c:
            r = await c.post("/api/v1/auth/login", json={"email": _EMAIL, "password": "x"})
        assert "/auth/login" in r.json()["instance"]
