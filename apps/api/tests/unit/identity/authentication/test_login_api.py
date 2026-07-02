"""
Presentation-layer tests for POST /api/v1/auth/login.

Test scope: the translation from HTTP → LoginUserCommand → HTTP response.
The application service is stubbed — no real infrastructure required.

Test categories:
  TestLoginSchemas          — Pydantic transport-level validation
  TestSuccessfulLogin       — 200, response shape, X-Request-ID header
  TestInvalidCredentials    — 401 AUTH_INVALID_CREDENTIALS
  TestAuthenticationFailed  — 401 AUTH_AUTHENTICATION_FAILED (risk block)
  TestEmailNotVerified      — 403 AUTH_EMAIL_NOT_VERIFIED
  TestAccountDisabled       — 403 AUTH_ACCOUNT_DISABLED
  TestAccountLocked         — 423 AUTH_ACCOUNT_LOCKED + Retry-After header
  TestValidationFailures    — 422 (missing/oversized fields)
  TestErrorResponseFormat   — RFC 7807 structure invariants
  TestSecurityInvariants    — sensitive fields never in responses
  TestDependencyInjection   — dependency override wiring

asyncio_mode = "auto" (pyproject.toml) — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.modules.identity.authentication.application.commands import LoginUserCommand
from app.modules.identity.authentication.application.dtos import AuthenticatedSessionSummary
from app.modules.identity.authentication.domain.errors import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticationFailedError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    PasswordHashingError,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.dependencies import get_login_service
from app.modules.identity.authentication.presentation.error_responses import map_login_failure
from app.modules.identity.authentication.presentation.schemas import (
    DataEnvelope,
    DeviceInfoRequest,
    LoginRequest,
    LoginResponse,
    SessionResponse,
    UserResponse,
)
from app.shared.domain.errors import ApplicationError, InfrastructureError
from app.shared.domain.result import Failure, Success

# ──────────────────────────────────────────────────────────────────────────── #
# Constants                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #

_VALID_EMAIL = "alice@example.com"
_STRONG_PASSWORD = "CorrectHorseBatteryStaple!"
_USER_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")
_SESSION_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")
_PLAIN_TOKEN = PlainRefreshToken.generate()
_ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.stub"
_FIXED_NOW = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
_ACCESS_EXPIRES_AT = _FIXED_NOW + timedelta(minutes=15)
_REFRESH_EXPIRES_AT = _FIXED_NOW + timedelta(days=7)

# ──────────────────────────────────────────────────────────────────────────── #
# Stubs                                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


def _success_summary() -> AuthenticatedSessionSummary:
    """Build an AuthenticatedSessionSummary for success scenarios."""
    return AuthenticatedSessionSummary(
        user_id=UserId(_USER_UUID),
        email=Email(_VALID_EMAIL),
        session_id=SessionId(_SESSION_UUID),
        access_token=_ACCESS_TOKEN,
        plain_refresh_token=_PLAIN_TOKEN,
        access_token_expires_at=_ACCESS_EXPIRES_AT,
        refresh_token_expires_at=_REFRESH_EXPIRES_AT,
        is_email_verified=True,
    )


class StubLoginService:
    """Configurable stub — returns a preset result for any command."""

    def __init__(self, result: Any) -> None:
        self._result = result
        self.received_command: LoginUserCommand | None = None

    async def execute(self, command: LoginUserCommand) -> Any:
        self.received_command = command
        return self._result


# ──────────────────────────────────────────────────────────────────────────── #
# Test app factory                                                              #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_test_app(stub_service: StubLoginService) -> FastAPI:
    """
    Build a minimal FastAPI test app with the auth router and a stubbed service.

    Uses RequestIDMiddleware so get_request_id() returns a value in tests.
    The router is mounted under /api/v1 (same as production).
    """
    from app.core.middleware.request_id import RequestIDMiddleware
    from app.modules.identity.authentication.presentation.router import router as auth_router

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    v1 = APIRouter(prefix="/api/v1")
    v1.include_router(auth_router)
    app.include_router(v1)

    app.dependency_overrides[get_login_service] = lambda: stub_service
    return app


async def _post_login(
    client: AsyncClient,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """Send a POST /api/v1/auth/login and return the response."""
    body = payload or {"email": _VALID_EMAIL, "password": _STRONG_PASSWORD}
    return await client.post(
        "/api/v1/auth/login",
        json=body,
        headers=headers or {},
    )


def _make_client(stub_service: StubLoginService) -> AsyncClient:
    """Return a configured AsyncClient (must be used as async context manager)."""
    app = _make_test_app(stub_service)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ──────────────────────────────────────────────────────────────────────────── #
# Schema tests                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestLoginSchemas:
    """Pydantic transport-level validation for LoginRequest."""

    def test_valid_minimal_request(self) -> None:
        req = LoginRequest(email="alice@example.com", password="ValidPassword1!")
        assert req.email == "alice@example.com"
        assert req.password == "ValidPassword1!"
        assert req.device_info is None
        assert req.locale is None
        assert req.timezone is None

    def test_email_whitespace_stripped(self) -> None:
        req = LoginRequest(email="  alice@example.com  ", password="ValidPassword1!")
        assert req.email == "alice@example.com"

    def test_password_whitespace_stripped(self) -> None:
        req = LoginRequest(email="alice@example.com", password="  ValidPassword1!  ")
        assert req.password == "ValidPassword1!"

    def test_email_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="a" * 255 + "@x.com", password="ValidPassword1!")

    def test_password_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="x" * 129)

    def test_email_min_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="", password="ValidPassword1!")

    def test_password_min_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="")

    def test_device_info_optional(self) -> None:
        req = LoginRequest(
            email="alice@example.com",
            password="ValidPassword1!",
            device_info=DeviceInfoRequest(device_name="Alice's iPhone", platform="ios"),
        )
        assert req.device_info is not None
        assert req.device_info.device_name == "Alice's iPhone"
        assert req.device_info.platform == "ios"

    def test_locale_optional(self) -> None:
        req = LoginRequest(email="a@b.com", password="pass", locale="en-US")
        assert req.locale == "en-US"

    def test_timezone_optional(self) -> None:
        req = LoginRequest(email="a@b.com", password="pass", timezone="America/New_York")
        assert req.timezone == "America/New_York"

    def test_locale_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="pass", locale="x" * 36)

    def test_timezone_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LoginRequest(email="a@b.com", password="pass", timezone="x" * 51)


# ──────────────────────────────────────────────────────────────────────────── #
# Successful login                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSuccessfulLogin:
    """POST /login returns 200 with the correct response shape."""

    async def test_status_200(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 200

    async def test_response_envelope(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = resp.json()
        assert "data" in body

    async def test_access_token_present(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["data"]["access_token"] == _ACCESS_TOKEN

    async def test_refresh_token_is_client_token(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        raw = resp.json()["data"]["refresh_token"]
        assert raw == _PLAIN_TOKEN.as_client_token()
        assert raw != "[REDACTED]"

    async def test_token_type_is_bearer(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["data"]["token_type"] == "Bearer"

    async def test_user_fields(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        user = resp.json()["data"]["user"]
        assert user["user_id"] == str(_USER_UUID)
        assert user["email"] == _VALID_EMAIL
        assert user["is_email_verified"] is True

    async def test_session_fields(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        session = resp.json()["data"]["session"]
        assert session["session_id"] == str(_SESSION_UUID)

    async def test_x_request_id_header_present(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert "x-request-id" in resp.headers

    async def test_device_name_in_session(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(
                client,
                payload={
                    "email": _VALID_EMAIL,
                    "password": _STRONG_PASSWORD,
                    "device_info": {"device_name": "Alice's iPhone", "platform": "ios"},
                },
            )
        assert resp.json()["data"]["session"]["device_name"] == "Alice's iPhone"

    async def test_command_built_correctly(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_login(
                client,
                payload={
                    "email": "  alice@example.com  ",
                    "password": _STRONG_PASSWORD,
                    "device_info": {"device_name": "My Phone", "platform": "android"},
                },
            )
        cmd = stub.received_command
        assert cmd is not None
        assert cmd.email == "alice@example.com"  # whitespace stripped by Pydantic
        assert cmd.device_name == "My Phone"
        assert cmd.platform == "android"

    async def test_expires_at_fields_present(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        data = resp.json()["data"]
        assert "access_token_expires_at" in data
        assert "refresh_token_expires_at" in data


# ──────────────────────────────────────────────────────────────────────────── #
# 401 — Invalid credentials                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class TestInvalidCredentials:
    """401 is returned for wrong email or password."""

    async def test_status_401(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 401

    async def test_error_code(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["error_code"] == "AUTH_INVALID_CREDENTIALS"

    async def test_generic_detail_message(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["detail"] == "Email or password is incorrect."

    async def test_problem_details_type(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert "invalid-credentials" in resp.json()["type"]

    async def test_x_request_id_present_on_failure(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        # trace_id is in the body; X-Request-ID is NOT added on failure paths
        assert "trace_id" in resp.json()


# ──────────────────────────────────────────────────────────────────────────── #
# 401 — Authentication failed (risk block)                                      #
# ──────────────────────────────────────────────────────────────────────────── #


class TestAuthenticationFailed:
    """401 is returned when risk assessment blocks the login."""

    async def test_status_401(self) -> None:
        stub = StubLoginService(Failure(AuthenticationFailedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 401

    async def test_error_code(self) -> None:
        stub = StubLoginService(Failure(AuthenticationFailedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["error_code"] == "AUTH_AUTHENTICATION_FAILED"


# ──────────────────────────────────────────────────────────────────────────── #
# 403 — Email not verified                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


class TestEmailNotVerified:
    """403 is returned when the user has not verified their email."""

    async def test_status_403(self) -> None:
        stub = StubLoginService(Failure(EmailNotVerifiedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 403

    async def test_error_code(self) -> None:
        stub = StubLoginService(Failure(EmailNotVerifiedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["error_code"] == "AUTH_EMAIL_NOT_VERIFIED"

    async def test_problem_details_type(self) -> None:
        stub = StubLoginService(Failure(EmailNotVerifiedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert "email-not-verified" in resp.json()["type"]


# ──────────────────────────────────────────────────────────────────────────── #
# 403 — Account disabled                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


class TestAccountDisabled:
    """403 is returned when the account has been permanently disabled."""

    async def test_status_403(self) -> None:
        stub = StubLoginService(Failure(AccountDisabledError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 403

    async def test_error_code(self) -> None:
        stub = StubLoginService(Failure(AccountDisabledError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["error_code"] == "AUTH_ACCOUNT_DISABLED"


# ──────────────────────────────────────────────────────────────────────────── #
# 423 — Account locked                                                          #
# ──────────────────────────────────────────────────────────────────────────── #


class TestAccountLocked:
    """423 is returned when the account is temporarily locked."""

    async def test_status_423(self) -> None:
        stub = StubLoginService(Failure(AccountLockedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 423

    async def test_error_code(self) -> None:
        stub = StubLoginService(Failure(AccountLockedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["error_code"] == "AUTH_ACCOUNT_LOCKED"

    async def test_problem_details_type(self) -> None:
        stub = StubLoginService(Failure(AccountLockedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert "account-locked" in resp.json()["type"]

    async def test_retry_after_header_when_locked_until_set(self) -> None:
        locked_until = datetime.now(UTC) + timedelta(minutes=15)
        stub = StubLoginService(Failure(AccountLockedError(locked_until=locked_until)))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert "retry-after" in resp.headers

    async def test_no_retry_after_header_when_locked_until_none(self) -> None:
        stub = StubLoginService(Failure(AccountLockedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert "retry-after" not in resp.headers

    async def test_locked_until_in_body(self) -> None:
        locked_until = datetime(2026, 7, 1, 12, 15, 0, tzinfo=UTC)
        stub = StubLoginService(Failure(AccountLockedError(locked_until=locked_until)))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = resp.json()
        assert body["locked_until"] is not None

    async def test_locked_until_null_when_not_set(self) -> None:
        stub = StubLoginService(Failure(AccountLockedError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["locked_until"] is None


# ──────────────────────────────────────────────────────────────────────────── #
# 503 — Infrastructure failures                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestServiceUnavailable:
    """503 is returned for infrastructure failures."""

    async def test_password_hashing_error_yields_503(self) -> None:
        stub = StubLoginService(Failure(PasswordHashingError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 503

    async def test_infrastructure_error_yields_503(self) -> None:
        stub = StubLoginService(Failure(InfrastructureError("DB unavailable")))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.status_code == 503

    async def test_error_code_service_unavailable(self) -> None:
        stub = StubLoginService(Failure(PasswordHashingError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["error_code"] == "AUTH_SERVICE_UNAVAILABLE"


# ──────────────────────────────────────────────────────────────────────────── #
# 422 — Transport validation failures                                            #
# ──────────────────────────────────────────────────────────────────────────── #


class TestValidationFailures:
    """422 is returned by FastAPI when the request body fails Pydantic validation."""

    async def test_missing_email_yields_422(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client, payload={"password": _STRONG_PASSWORD})
        assert resp.status_code == 422

    async def test_missing_password_yields_422(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client, payload={"email": _VALID_EMAIL})
        assert resp.status_code == 422

    async def test_empty_email_yields_422(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(
                client, payload={"email": "", "password": _STRONG_PASSWORD}
            )
        assert resp.status_code == 422

    async def test_empty_password_yields_422(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(
                client, payload={"email": _VALID_EMAIL, "password": ""}
            )
        assert resp.status_code == 422

    async def test_oversized_email_yields_422(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(
                client,
                payload={"email": "a" * 250 + "@b.com", "password": _STRONG_PASSWORD},
            )
        assert resp.status_code == 422

    async def test_oversized_password_yields_422(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(
                client,
                payload={"email": _VALID_EMAIL, "password": "x" * 129},
            )
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────── #
# RFC 7807 structure invariants                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestErrorResponseFormat:
    """All error responses include the required RFC 7807 fields."""

    @pytest.mark.parametrize(
        "error",
        [
            InvalidCredentialsError(),
            EmailNotVerifiedError(),
            AccountLockedError(),
            AccountDisabledError(),
            AuthenticationFailedError(),
            PasswordHashingError(),
        ],
    )
    async def test_problem_details_fields_present(self, error: Any) -> None:
        stub = StubLoginService(Failure(error))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = resp.json()
        for field in ("type", "title", "status", "detail", "instance", "error_code", "trace_id"):
            assert field in body, f"Missing RFC 7807 field: {field}"

    async def test_instance_is_login_path(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["instance"] == "/api/v1/auth/login"

    async def test_status_field_matches_http_status(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["status"] == resp.status_code

    async def test_type_uses_travix_error_base(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert resp.json()["type"].startswith("https://errors.travix.ai/auth/")

    async def test_trace_id_is_valid_uuid(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        trace_id = resp.json()["trace_id"]
        uuid.UUID(trace_id)  # raises ValueError if not a UUID


# ──────────────────────────────────────────────────────────────────────────── #
# Security invariants                                                            #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSecurityInvariants:
    """Sensitive fields must never appear in any HTTP response."""

    async def test_password_not_in_success_response(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = str(resp.json())
        assert _STRONG_PASSWORD not in body

    async def test_access_token_not_in_error_response(self) -> None:
        stub = StubLoginService(Failure(InvalidCredentialsError()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        assert _ACCESS_TOKEN not in str(resp.json())

    async def test_refresh_token_repr_not_in_response(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = str(resp.json())
        assert "[REDACTED]" not in body

    async def test_error_response_does_not_leak_internal_message(self) -> None:
        stub = StubLoginService(Failure(PasswordHashingError("Argon2 segfault")))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = str(resp.json())
        assert "Argon2" not in body
        assert "segfault" not in body

    async def test_401_message_generic_regardless_of_error_detail(self) -> None:
        stub = StubLoginService(
            Failure(InvalidCredentialsError("INTERNAL: no record for hash abc123"))
        )
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        body = resp.json()
        assert "abc123" not in str(body)
        assert body["detail"] == "Email or password is incorrect."

    async def test_refresh_token_in_success_response_is_safe_value(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_login(client)
        token = resp.json()["data"]["refresh_token"]
        assert token == _PLAIN_TOKEN.as_client_token()
        assert len(token) > 10


# ──────────────────────────────────────────────────────────────────────────── #
# Dependency injection                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestDependencyInjection:
    """Verify that dependency_overrides reach the route handler."""

    async def test_stub_service_is_called(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_login(client)
        assert stub.received_command is not None

    async def test_overriding_with_different_result_changes_response(self) -> None:
        stub_ok = StubLoginService(Success(_success_summary()))
        stub_fail = StubLoginService(Failure(InvalidCredentialsError()))

        async with _make_client(stub_ok) as client:
            resp_ok = await _post_login(client)
        async with _make_client(stub_fail) as client:
            resp_fail = await _post_login(client)

        assert resp_ok.status_code == 200
        assert resp_fail.status_code == 401

    async def test_command_carries_ip_from_request(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_login(
                client,
                headers={"X-Forwarded-For": "203.0.113.5"},
            )
        cmd = stub.received_command
        assert cmd is not None
        assert cmd.ip_address == "203.0.113.5"

    async def test_command_carries_user_agent_from_request(self) -> None:
        stub = StubLoginService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_login(
                client,
                headers={"User-Agent": "TravixApp/1.0 iOS/17.4"},
            )
        cmd = stub.received_command
        assert cmd is not None
        assert cmd.user_agent == "TravixApp/1.0 iOS/17.4"
