"""
Presentation-layer tests for POST /api/v1/auth/register.

Test scope: the translation from HTTP → RegisterUserCommand → HTTP response.
The application service is stubbed — no real infrastructure required.

Test categories:
  TestSchemas              — Pydantic transport-level validation
  TestRequestContext       — Header extraction, IP parsing, received_at
  TestSuccessVerification  — 201 with requires_verification: true (production)
  TestSuccessAutoLogin     — 201 with requires_verification: false (dev/CI)
  TestEmailInvalid         — 422 AUTH_EMAIL_INVALID
  TestPasswordTooWeak      — 422 AUTH_PASSWORD_TOO_WEAK (+ violations)
  TestEmailAlreadyExists   — 409 AUTH_EMAIL_ALREADY_EXISTS
  TestServiceUnavailable   — 503 (PasswordHashingError / InfrastructureError)
  TestInternalError        — 500 (unexpected TravixError)
  TestErrorResponseFormat  — RFC 7807 structure invariants
  TestSecurityInvariants   — sensitive fields never in responses
  TestOpenAPISchema        — OpenAPI document completeness
  TestDependencyInjection  — dependency override wiring

asyncio_mode = "auto" (pyproject.toml) — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from fastapi.routing import APIRouter

from app.modules.identity.authentication.application.commands import RegisterUserCommand
from app.modules.identity.authentication.application.dtos import RegistrationSummary
from app.modules.identity.authentication.domain.errors import (
    EmailAlreadyExistsError,
    InvalidEmailError,
    PasswordHashingError,
    WeakPasswordError,
)
from app.modules.identity.authentication.domain.value_objects.email import Email
from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.session_id import SessionId
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.dependencies import (
    get_registration_service,
)
from app.modules.identity.authentication.presentation.error_responses import (
    RateLimitInfo,
    add_rate_limit_headers,
    build_rate_limit_response,
    map_registration_failure,
)
from app.modules.identity.authentication.presentation.request_context import (
    _extract_client_ip,
)
from app.modules.identity.authentication.presentation.schemas import (
    DataEnvelope,
    DeviceInfoRequest,
    RegisterRequest,
    RegisterResponse,
    SessionResponse,
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

# ──────────────────────────────────────────────────────────────────────────── #
# Stubs                                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


def _success_summary(
    *,
    requires_email_verification: bool = True,
    session_created: bool = False,
) -> RegistrationSummary:
    """Build a RegistrationSummary for success scenarios."""
    session_id = SessionId(_SESSION_UUID) if session_created else None
    access_token = _ACCESS_TOKEN if session_created else None
    plain_refresh = _PLAIN_TOKEN if session_created else None

    return RegistrationSummary(
        user_id=UserId(_USER_UUID),
        email=Email(_VALID_EMAIL),
        is_email_verified=not requires_email_verification,
        session_created=session_created,
        requires_email_verification=requires_email_verification,
        session_id=session_id,
        access_token=access_token,
        plain_refresh_token=plain_refresh,
    )


class StubRegistrationService:
    """Configurable stub — returns a preset result for any command."""

    def __init__(self, result: Any) -> None:
        self._result = result
        self.received_command: RegisterUserCommand | None = None

    async def execute(self, command: RegisterUserCommand) -> Any:
        self.received_command = command
        return self._result


# ──────────────────────────────────────────────────────────────────────────── #
# Test app factory                                                              #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_test_app(stub_service: StubRegistrationService) -> FastAPI:
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

    app.dependency_overrides[get_registration_service] = lambda: stub_service
    return app


async def _post_register(
    client: AsyncClient,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """Send a POST /api/v1/auth/register and return the response."""
    body = payload or {"email": _VALID_EMAIL, "password": _STRONG_PASSWORD}
    return await client.post(
        "/api/v1/auth/register",
        json=body,
        headers=headers or {},
    )


def _make_client(stub_service: StubRegistrationService) -> AsyncClient:
    """Return a configured AsyncClient (must be used as async context manager)."""
    app = _make_test_app(stub_service)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


# ──────────────────────────────────────────────────────────────────────────── #
# Schema tests                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSchemas:
    """Pydantic transport-level validation for RegisterRequest."""

    def test_valid_minimal_request(self) -> None:
        req = RegisterRequest(email="alice@example.com", password="ValidPassword1!")
        assert req.email == "alice@example.com"
        assert req.password == "ValidPassword1!"
        assert req.device_info is None

    def test_email_whitespace_stripped(self) -> None:
        req = RegisterRequest(email="  alice@example.com  ", password="ValidPassword1!")
        assert req.email == "alice@example.com"

    def test_password_whitespace_stripped(self) -> None:
        req = RegisterRequest(email="alice@example.com", password="  ValidPassword1!  ")
        assert req.password == "ValidPassword1!"

    def test_email_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(email="a" * 255 + "@x.com", password="ValidPassword1!")

    def test_password_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="x" * 129)

    def test_email_min_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(email="", password="ValidPassword1!")

    def test_password_min_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RegisterRequest(email="a@b.com", password="")

    def test_device_info_optional(self) -> None:
        req = RegisterRequest(
            email="alice@example.com",
            password="ValidPassword1!",
            device_info=DeviceInfoRequest(
                device_name="Alice's iPhone",
                platform="ios",
                app_version="1.0.0",
                os_version="iOS 17.4",
            ),
        )
        assert req.device_info is not None
        assert req.device_info.device_name == "Alice's iPhone"
        assert req.device_info.platform == "ios"

    def test_device_info_platform_validation(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DeviceInfoRequest(platform="windows")  # type: ignore[arg-type]

    def test_device_name_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DeviceInfoRequest(device_name="x" * 101)

    def test_app_version_max_length_enforced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DeviceInfoRequest(app_version="1." + "0" * 20)

    def test_register_response_requires_verification(self) -> None:
        resp = RegisterResponse(
            user_id="abc",
            email="alice@example.com",
            requires_verification=True,
            message="Check your email.",
        )
        assert resp.access_token is None
        assert resp.refresh_token is None
        assert resp.session is None

    def test_data_envelope_wraps_payload(self) -> None:
        inner = RegisterResponse(
            user_id="abc",
            email="a@b.com",
            requires_verification=True,
        )
        env = DataEnvelope(data=inner)
        dumped = env.model_dump(mode="json")
        assert "data" in dumped
        assert dumped["data"]["user_id"] == "abc"


# ──────────────────────────────────────────────────────────────────────────── #
# RequestContext tests                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestRequestContext:
    """Verify header extraction in _extract_client_ip and RequestContext."""

    def test_ip_from_x_forwarded_for(self) -> None:
        req = MagicMock()
        req.headers = {"X-Forwarded-For": "203.0.113.1, 10.0.0.1"}
        req.client = None
        assert _extract_client_ip(req) == "203.0.113.1"

    def test_ip_from_x_real_ip(self) -> None:
        req = MagicMock()
        req.headers = {"X-Real-IP": "  203.0.113.2  "}
        req.client = None
        assert _extract_client_ip(req) == "203.0.113.2"

    def test_ip_from_client_host(self) -> None:
        req = MagicMock()
        req.headers = {}
        req.client = MagicMock()
        req.client.host = "192.168.1.1"
        assert _extract_client_ip(req) == "192.168.1.1"

    def test_ip_none_when_no_source(self) -> None:
        req = MagicMock()
        req.headers = {}
        req.client = None
        assert _extract_client_ip(req) is None

    def test_forwarded_for_prefers_leftmost(self) -> None:
        req = MagicMock()
        req.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8, 9.10.11.12"}
        req.client = None
        assert _extract_client_ip(req) == "1.2.3.4"

    async def test_context_created_successfully(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            response = await _post_register(client)
        assert response.status_code == 201

    async def test_x_request_id_header_echoed(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            response = await _post_register(
                client,
                headers={"X-Request-ID": "my-custom-request-id"},
            )
        assert "x-request-id" in response.headers


# ──────────────────────────────────────────────────────────────────────────── #
# 201 — verification required (production default)                              #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSuccessVerificationRequired:
    """POST /register → 201 with requires_verification: true."""

    async def test_status_code(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 201

    async def test_response_shape(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert data["user_id"] == str(_USER_UUID)
        assert data["email"] == _VALID_EMAIL
        assert data["requires_verification"] is True
        assert "message" in data
        assert data["message"]

    async def test_no_tokens_in_response(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        data = resp.json()["data"]
        assert data.get("access_token") is None
        assert data.get("refresh_token") is None
        assert data.get("token_type") is None
        assert data.get("session") is None

    async def test_command_built_from_body(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            await _post_register(
                client,
                payload={
                    "email": "  BOB@EXAMPLE.COM  ",
                    "password": _STRONG_PASSWORD,
                    "device_info": {"platform": "android"},
                },
            )
        cmd = stub.received_command
        assert cmd is not None
        # Pydantic strips whitespace but preserves case (case-folding is domain)
        assert cmd.email == "BOB@EXAMPLE.COM"
        assert cmd.platform == "android"
        assert cmd.create_session is True

    async def test_x_request_id_in_response_headers(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert "x-request-id" in resp.headers

    async def test_device_name_passed_to_command(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            await _post_register(
                client,
                payload={
                    "email": _VALID_EMAIL,
                    "password": _STRONG_PASSWORD,
                    "device_info": {"device_name": "Alice's iPhone 15 Pro"},
                },
            )
        assert stub.received_command is not None
        assert stub.received_command.device_name == "Alice's iPhone 15 Pro"

    async def test_ip_address_passed_to_command(self) -> None:
        stub = StubRegistrationService(
            Success(_success_summary(requires_email_verification=True))
        )
        async with _make_client(stub) as client:
            await _post_register(
                client,
                headers={"X-Forwarded-For": "1.2.3.4"},
            )
        assert stub.received_command is not None
        assert stub.received_command.ip_address == "1.2.3.4"


# ──────────────────────────────────────────────────────────────────────────── #
# 201 — auto-login (dev/CI)                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSuccessAutoLogin:
    """POST /register → 201 with requires_verification: false (dev/CI)."""

    async def test_status_code(self) -> None:
        stub = StubRegistrationService(
            Success(
                _success_summary(
                    requires_email_verification=False, session_created=True
                )
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 201

    async def test_tokens_present(self) -> None:
        stub = StubRegistrationService(
            Success(
                _success_summary(
                    requires_email_verification=False, session_created=True
                )
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        data = resp.json()["data"]
        assert data["requires_verification"] is False
        assert data["access_token"] == _ACCESS_TOKEN
        assert data["refresh_token"] == _PLAIN_TOKEN.as_client_token()
        assert data["token_type"] == "Bearer"
        assert data["access_token_expires_at"] is not None
        assert data["refresh_token_expires_at"] is not None

    async def test_session_object_present(self) -> None:
        stub = StubRegistrationService(
            Success(
                _success_summary(
                    requires_email_verification=False, session_created=True
                )
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(
                client,
                payload={
                    "email": _VALID_EMAIL,
                    "password": _STRONG_PASSWORD,
                    "device_info": {"device_name": "Test Device"},
                },
            )
        data = resp.json()["data"]
        assert data["session"] is not None
        assert data["session"]["session_id"] == str(_SESSION_UUID)
        assert data["session"]["device_name"] == "Test Device"
        assert data["session"]["created_at"] is not None

    async def test_session_device_name_null_when_no_device_info(self) -> None:
        stub = StubRegistrationService(
            Success(
                _success_summary(
                    requires_email_verification=False, session_created=True
                )
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        data = resp.json()["data"]
        assert data["session"]["device_name"] is None

    async def test_refresh_token_is_raw_value(self) -> None:
        """The refresh token in the response must be the raw client-safe value."""
        stub = StubRegistrationService(
            Success(
                _success_summary(
                    requires_email_verification=False, session_created=True
                )
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        raw = resp.json()["data"]["refresh_token"]
        assert raw == _PLAIN_TOKEN.as_client_token()
        # The raw value must NOT be the repr — it should be the actual token
        assert "[REDACTED]" not in raw


# ──────────────────────────────────────────────────────────────────────────── #
# 422 — invalid email                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestEmailInvalid:
    """POST /register → 422 AUTH_EMAIL_INVALID."""

    async def test_status_code(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 422

    async def test_error_code(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        body = resp.json()
        assert body["error_code"] == "VALIDATION_ERROR"
        assert any(
            e["error_code"] == "AUTH_EMAIL_INVALID" for e in body["errors"]
        )

    async def test_field_is_email(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        errors = resp.json()["errors"]
        assert any(e["field"] == "email" for e in errors)

    async def test_rfc7807_structure(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        body = resp.json()
        for key in ("type", "title", "status", "detail", "instance", "trace_id"):
            assert key in body, f"RFC 7807 field '{key}' missing"

    async def test_type_uri_matches_contract(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.json()["type"] == "https://errors.travix.ai/validation-error"

    async def test_instance_is_register_path(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.json()["instance"] == "/api/v1/auth/register"


# ──────────────────────────────────────────────────────────────────────────── #
# 422 — weak password                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestPasswordTooWeak:
    """POST /register → 422 AUTH_PASSWORD_TOO_WEAK."""

    async def test_status_code(self) -> None:
        stub = StubRegistrationService(
            Failure(WeakPasswordError(violations=["Must be at least 12 characters"]))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 422

    async def test_error_code(self) -> None:
        stub = StubRegistrationService(
            Failure(WeakPasswordError(violations=["Too short"]))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        body = resp.json()
        assert any(
            e["error_code"] == "AUTH_PASSWORD_TOO_WEAK" for e in body["errors"]
        )

    async def test_violations_array_present(self) -> None:
        violations = ["Must be at least 12 characters", "Must not be a common password"]
        stub = StubRegistrationService(Failure(WeakPasswordError(violations=violations)))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        errors = resp.json()["errors"]
        pw_error = next(e for e in errors if e["error_code"] == "AUTH_PASSWORD_TOO_WEAK")
        assert pw_error["violations"] == violations

    async def test_field_is_password(self) -> None:
        stub = StubRegistrationService(
            Failure(WeakPasswordError(violations=["Too short"]))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        errors = resp.json()["errors"]
        assert any(e["field"] == "password" for e in errors)


# ──────────────────────────────────────────────────────────────────────────── #
# 409 — email already exists                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestEmailAlreadyExists:
    """POST /register → 409 AUTH_EMAIL_ALREADY_EXISTS."""

    async def test_status_code(self) -> None:
        stub = StubRegistrationService(Failure(EmailAlreadyExistsError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 409

    async def test_error_code(self) -> None:
        stub = StubRegistrationService(Failure(EmailAlreadyExistsError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.json()["error_code"] == "AUTH_EMAIL_ALREADY_EXISTS"

    async def test_type_uri_matches_contract(self) -> None:
        stub = StubRegistrationService(Failure(EmailAlreadyExistsError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert "email-already-exists" in resp.json()["type"]

    async def test_detail_does_not_echo_email(self) -> None:
        """The error detail must not echo the submitted email (enumeration prevention)."""
        stub = StubRegistrationService(Failure(EmailAlreadyExistsError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client, payload={"email": _VALID_EMAIL, "password": _STRONG_PASSWORD})
        body = resp.json()
        assert _VALID_EMAIL not in body.get("detail", "")


# ──────────────────────────────────────────────────────────────────────────── #
# 503 — service unavailable                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class TestServiceUnavailable:
    """POST /register → 503 on infrastructure failures."""

    async def test_password_hashing_error_returns_503(self) -> None:
        stub = StubRegistrationService(Failure(PasswordHashingError("Argon2 failed.")))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 503

    async def test_infrastructure_error_returns_503(self) -> None:
        stub = StubRegistrationService(
            Failure(InfrastructureError("DB connection lost."))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 503

    async def test_error_code(self) -> None:
        stub = StubRegistrationService(Failure(PasswordHashingError("Argon2 failed.")))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.json()["error_code"] == "AUTH_SERVICE_UNAVAILABLE"

    async def test_internal_cause_not_in_response(self) -> None:
        """The internal error message must NOT be leaked to the client."""
        stub = StubRegistrationService(
            Failure(InfrastructureError("PostgreSQL: SSL_ERROR_RX_RECORD_TOO_LONG"))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        body = resp.json()
        assert "PostgreSQL" not in body.get("detail", "")
        assert "SSL_ERROR" not in str(body)


# ──────────────────────────────────────────────────────────────────────────── #
# 422 — Pydantic transport-level validation (FastAPI layer)                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestTransportValidation:
    """FastAPI / Pydantic rejects malformed requests before the handler runs."""

    async def test_missing_email_returns_422(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"password": _STRONG_PASSWORD},
            )
        assert resp.status_code == 422
        assert stub.received_command is None

    async def test_missing_password_returns_422(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                json={"email": _VALID_EMAIL},
            )
        assert resp.status_code == 422
        assert stub.received_command is None

    async def test_empty_body_returns_422(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await client.post(
                "/api/v1/auth/register",
                content=b"",
                headers={"Content-Type": "application/json"},
            )
        assert resp.status_code == 422

    async def test_password_exceeds_128_chars_returns_422(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_register(
                client,
                payload={"email": _VALID_EMAIL, "password": "x" * 129},
            )
        assert resp.status_code == 422
        assert stub.received_command is None

    async def test_invalid_device_platform_returns_422(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_register(
                client,
                payload={
                    "email": _VALID_EMAIL,
                    "password": _STRONG_PASSWORD,
                    "device_info": {"platform": "linux"},
                },
            )
        assert resp.status_code == 422


# ──────────────────────────────────────────────────────────────────────────── #
# Error response format invariants                                              #
# ──────────────────────────────────────────────────────────────────────────── #


class TestErrorResponseFormat:
    """All error responses must comply with RFC 7807 Problem Details."""

    @pytest.mark.parametrize(
        "error, expected_status",
        [
            (InvalidEmailError(), 422),
            (WeakPasswordError(violations=["too short"]), 422),
            (EmailAlreadyExistsError(), 409),
            (PasswordHashingError("fail"), 503),
            (InfrastructureError("db fail"), 503),
        ],
    )
    async def test_rfc7807_required_fields(
        self, error: Exception, expected_status: int
    ) -> None:
        stub = StubRegistrationService(Failure(error))  # type: ignore[arg-type]
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == expected_status
        body = resp.json()
        for field in ("type", "title", "status", "detail", "instance", "error_code", "trace_id"):
            assert field in body, f"RFC 7807 required field '{field}' missing"

    async def test_trace_id_is_uuid_string(self) -> None:
        stub = StubRegistrationService(Failure(EmailAlreadyExistsError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        trace_id = resp.json()["trace_id"]
        # Must be parseable as a UUID
        uuid.UUID(trace_id)

    async def test_status_field_matches_http_status(self) -> None:
        for error, http_status in [
            (InvalidEmailError(), 422),
            (EmailAlreadyExistsError(), 409),
            (PasswordHashingError("fail"), 503),
        ]:
            stub = StubRegistrationService(Failure(error))  # type: ignore[arg-type]
            async with _make_client(stub) as client:
                resp = await _post_register(client)
            assert resp.json()["status"] == http_status

    async def test_instance_is_always_register_path(self) -> None:
        for error in (InvalidEmailError(), EmailAlreadyExistsError()):
            stub = StubRegistrationService(Failure(error))
            async with _make_client(stub) as client:
                resp = await _post_register(client)
            assert resp.json()["instance"] == "/api/v1/auth/register"

    async def test_type_uri_starts_with_travix_errors_domain(self) -> None:
        stub = StubRegistrationService(Failure(EmailAlreadyExistsError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.json()["type"].startswith("https://errors.travix.ai/")


# ──────────────────────────────────────────────────────────────────────────── #
# Security invariants                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestSecurityInvariants:
    """Sensitive data must never appear in HTTP responses."""

    async def test_password_not_in_any_response_field(self) -> None:
        """The submitted password must never appear in any response body."""
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            resp = await _post_register(
                client,
                payload={"email": _VALID_EMAIL, "password": "super-secret-pw-123!"},
            )
        assert "super-secret-pw-123!" not in resp.text

    async def test_refresh_token_repr_not_in_response(self) -> None:
        """[REDACTED] (the repr of PlainRefreshToken) must not appear in the body."""
        stub = StubRegistrationService(
            Success(
                _success_summary(requires_email_verification=False, session_created=True)
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert "[REDACTED]" not in resp.text

    async def test_raw_refresh_token_is_present_in_auto_login_response(self) -> None:
        """When tokens are issued, the raw token value (not repr) must be present."""
        stub = StubRegistrationService(
            Success(
                _success_summary(requires_email_verification=False, session_created=True)
            )
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        token = resp.json()["data"]["refresh_token"]
        assert token == _PLAIN_TOKEN.as_client_token()

    async def test_503_detail_does_not_leak_internal_message(self) -> None:
        stub = StubRegistrationService(
            Failure(PasswordHashingError("argon2id library error: ENOMEM"))
        )
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert "argon2id" not in resp.text.lower()
        assert "ENOMEM" not in resp.text

    async def test_500_detail_does_not_leak_stack_trace(self) -> None:
        stub = StubRegistrationService(Failure(ApplicationError("boom")))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 500
        assert "boom" not in resp.text
        assert "Traceback" not in resp.text


# ──────────────────────────────────────────────────────────────────────────── #
# Error response helper unit tests                                              #
# ──────────────────────────────────────────────────────────────────────────── #


class TestErrorHelpers:
    """Unit tests for the error_responses module functions."""

    def test_map_registration_failure_invalid_email(self) -> None:
        resp = map_registration_failure(
            InvalidEmailError(), trace_id="abc", instance="/test"
        )
        assert resp.status_code == 422

    def test_map_registration_failure_weak_password_includes_violations(self) -> None:
        import json

        resp = map_registration_failure(
            WeakPasswordError(violations=["v1", "v2"]),
            trace_id="abc",
            instance="/test",
        )
        body = json.loads(resp.body)
        pw = next(e for e in body["errors"] if e["error_code"] == "AUTH_PASSWORD_TOO_WEAK")
        assert pw["violations"] == ["v1", "v2"]

    def test_map_registration_failure_conflict(self) -> None:
        resp = map_registration_failure(
            EmailAlreadyExistsError(), trace_id="abc", instance="/test"
        )
        assert resp.status_code == 409

    def test_map_registration_failure_hashing_error(self) -> None:
        resp = map_registration_failure(
            PasswordHashingError("fail"), trace_id="abc", instance="/test"
        )
        assert resp.status_code == 503

    def test_map_registration_failure_infrastructure_error(self) -> None:
        resp = map_registration_failure(
            InfrastructureError("db"), trace_id="abc", instance="/test"
        )
        assert resp.status_code == 503

    def test_map_registration_failure_unknown_error_returns_500(self) -> None:
        from app.shared.domain.errors import TravixError

        class UnknownError(TravixError):
            pass

        resp = map_registration_failure(
            UnknownError("unexpected"), trace_id="abc", instance="/test"
        )
        assert resp.status_code == 500

    def test_rate_limit_info_dataclass(self) -> None:
        info = RateLimitInfo(limit=5, remaining=4, reset_unix=1_700_000_000)
        assert info.limit == 5
        assert info.remaining == 4
        assert info.retry_after_seconds is None

    def test_add_rate_limit_headers(self) -> None:
        headers: dict[str, str] = {}
        info = RateLimitInfo(
            limit=5, remaining=0, reset_unix=1_700_000_000, retry_after_seconds=3600
        )
        add_rate_limit_headers(headers, info)
        assert headers["X-RateLimit-Limit"] == "5"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert headers["Retry-After"] == "3600"

    def test_build_rate_limit_response(self) -> None:
        import json

        resp = build_rate_limit_response(trace_id="abc", retry_after_seconds=3600)
        assert resp.status_code == 429
        body = json.loads(resp.body)
        assert body["error_code"] == "AUTH_RATE_LIMITED"
        assert body["retry_after_seconds"] == 3600


# ──────────────────────────────────────────────────────────────────────────── #
# OpenAPI schema tests                                                          #
# ──────────────────────────────────────────────────────────────────────────── #


class TestOpenAPISchema:
    """Verify the OpenAPI document is generated and contains required elements."""

    async def test_openapi_endpoint_accessible(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        app = _make_test_app(stub)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.get("/openapi.json")
        assert resp.status_code == 200

    async def test_register_path_in_schema(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        app = _make_test_app(stub)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/auth/register" in schema["paths"]

    async def test_operation_id_is_register_user(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        app = _make_test_app(stub)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
        post_op = schema["paths"]["/api/v1/auth/register"]["post"]
        assert post_op["operationId"] == "registerUser"

    async def test_response_codes_documented(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        app = _make_test_app(stub)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
        responses = schema["paths"]["/api/v1/auth/register"]["post"]["responses"]
        for code in ("201", "409", "422", "429", "500", "503"):
            assert code in responses, f"HTTP {code} not documented in OpenAPI"

    async def test_tags_include_authentication(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        app = _make_test_app(stub)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            schema = (await client.get("/openapi.json")).json()
        post_op = schema["paths"]["/api/v1/auth/register"]["post"]
        assert "Authentication" in post_op["tags"]


# ──────────────────────────────────────────────────────────────────────────── #
# Dependency injection tests                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestDependencyInjection:
    """Verify the dependency override pattern works correctly."""

    async def test_stub_service_is_called(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_register(client)
        assert stub.received_command is not None

    async def test_real_service_not_called_when_overridden(self) -> None:
        stub = StubRegistrationService(Failure(InvalidEmailError()))
        async with _make_client(stub) as client:
            resp = await _post_register(client)
        assert resp.status_code == 422
        assert stub.received_command is not None

    async def test_command_email_matches_body(self) -> None:
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_register(
                client, payload={"email": "bob@example.com", "password": _STRONG_PASSWORD}
            )
        assert stub.received_command is not None
        assert stub.received_command.email == "bob@example.com"

    async def test_command_password_passed_to_service(self) -> None:
        """Verify the password is forwarded to the service (not filtered)."""
        stub = StubRegistrationService(Success(_success_summary()))
        async with _make_client(stub) as client:
            await _post_register(
                client, payload={"email": _VALID_EMAIL, "password": "MySecretPw123!"}
            )
        assert stub.received_command is not None
        assert stub.received_command.password == "MySecretPw123!"
