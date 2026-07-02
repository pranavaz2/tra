"""
Unit tests for the authorization middleware dependencies.

Test scope: Bearer token extraction, JWT validation, revocation checking,
AuthorizationContext population, and error response format.

The real HS256JWTService is used for token creation and validation — no
stub JWT service is needed, as the service has no external dependencies.

Test categories:
  TestAuthorizationContextCreation   — dataclass shape and all fields
  TestValidToken                     — successful auth → AuthorizationContext
  TestMissingToken                   — absent header → 401 AUTH_TOKEN_MISSING
  TestMalformedHeader                — bad format → 401 AUTH_TOKEN_MALFORMED
  TestExpiredToken                   — past exp → 401 AUTH_TOKEN_EXPIRED
  TestInvalidSignature               — wrong key → 401 AUTH_TOKEN_INVALID
  TestRevokedToken                   — revocation checker True → 401 AUTH_TOKEN_REVOKED
  TestOptionalAuthentication         — None on missing, context on valid, 401 on malformed
  TestDependencyInjection            — override wiring works
  TestErrorResponseFormat            — RFC 7807 structure invariants

asyncio_mode = "auto" (pyproject.toml) — no @pytest.mark.asyncio needed.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.middleware.request_id import RequestIDMiddleware
from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import (
    OptionalAuthentication,
    RequireAuthentication,
    get_token_revocation_checker,
)
from app.core.security.auth.errors import AuthorizationError
from app.core.security.auth.revocation import NullTokenRevocationChecker
from app.core.security.jwt.claims import AccessTokenClaims
from app.core.security.jwt.dependencies import get_jwt_service
from app.core.security.jwt.interfaces import JWTService
from app.core.security.jwt.service import HS256JWTService
from app.core.security.jwt.signing import InMemorySigningKeyProvider, SigningKey

# ──────────────────────────────────────────────────────────────────────────── #
# Test constants                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #

_SECRET = "test-signing-secret-must-be-at-least-32-chars!!"
_BAD_SECRET = "completely-different-secret-must-be-at-least-32!"
_KID = "test-v1"
_ISSUER = "https://api.travix.ai"
_AUDIENCE = "travix-mobile"
_USER_ID = str(uuid.UUID("00000000-0000-4000-8000-000000000001"))
_SESSION_ID = str(uuid.UUID("00000000-0000-4000-8000-000000000002"))
_JTI = str(uuid.UUID("00000000-0000-4000-8000-000000000003"))
_EMAIL = "alice@example.com"

# ──────────────────────────────────────────────────────────────────────────── #
# JWT service helpers                                                            #
# ──────────────────────────────────────────────────────────────────────────── #


def _signing_key(secret: str = _SECRET) -> SigningKey:
    return SigningKey(
        kid=_KID, algorithm="HS256", secret=SecretStr(secret), is_primary=True
    )


def _jwt_service(secret: str = _SECRET) -> HS256JWTService:
    provider = InMemorySigningKeyProvider(_signing_key(secret))
    return HS256JWTService(
        signing_key_provider=provider,
        issuer=_ISSUER,
        audience=_AUDIENCE,
        algorithm="HS256",
        leeway_seconds=0,
        access_token_lifetime_minutes=15,
    )


def _claims(*, exp_offset_minutes: float = 15) -> AccessTokenClaims:
    now = datetime.now(UTC)
    return AccessTokenClaims(
        sub=_USER_ID,
        jti=_JTI,
        iat=now,
        exp=now + timedelta(minutes=exp_offset_minutes),
        nbf=now,
        iss=_ISSUER,
        aud=_AUDIENCE,
        sid=_SESSION_ID,
        email=_EMAIL,
        verified=True,
        token_version=1,
        session_version=1,
    )


def _valid_token(secret: str = _SECRET) -> str:
    svc = _jwt_service(secret)
    return svc.create_access_token(_claims())


def _expired_token() -> str:
    svc = _jwt_service()
    claims = _claims(exp_offset_minutes=-1)
    return svc.create_access_token(claims)


def _token_signed_with_wrong_key() -> str:
    return _valid_token(secret=_BAD_SECRET)


# ──────────────────────────────────────────────────────────────────────────── #
# Stub revocation checker                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


class _AlwaysRevokedChecker:
    """Reports every JTI as revoked — simulates a full blacklist."""

    async def is_revoked(self, jti: str) -> bool:
        return True

    async def revoke(self, jti: str, expires_at: datetime) -> None:
        pass


# ──────────────────────────────────────────────────────────────────────────── #
# Test app factory                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_test_app(
    *,
    jwt_service: JWTService | None = None,
    revocation_checker: Any = None,
) -> FastAPI:
    """
    Build a minimal FastAPI test app with:
      GET /protected  → RequireAuthentication (returns auth context as JSON)
      GET /optional   → OptionalAuthentication (returns context or null)
      GET /user       → CurrentUser string

    AuthorizationError handler is registered so RFC 7807 responses are produced.
    RequestIDMiddleware provides a trace_id for error responses.
    """
    from app.core.security.auth.errors import AuthorizationError

    async def _auth_error_handler(
        request: Any,  # noqa: ANN001
        exc: AuthorizationError,
    ) -> JSONResponse:
        return exc.to_response()

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(AuthorizationError, _auth_error_handler)  # type: ignore[arg-type]

    router = APIRouter()

    @router.get("/protected")
    async def protected_route(auth: RequireAuthentication) -> dict[str, Any]:
        return {
            "user_id": auth.user_id,
            "session_id": auth.session_id,
            "token_id": auth.token_id,
            "token_version": auth.token_version,
            "session_version": auth.session_version,
            "authentication_method": auth.authentication_method,
            "email": auth.email,
            "is_email_verified": auth.is_email_verified,
        }

    @router.get("/optional")
    async def optional_route(auth: OptionalAuthentication) -> dict[str, Any]:
        if auth is None:
            return {"authenticated": False}
        return {"authenticated": True, "user_id": auth.user_id}

    app.include_router(router)

    if jwt_service is not None:
        app.dependency_overrides[get_jwt_service] = lambda: jwt_service
    else:
        app.dependency_overrides[get_jwt_service] = lambda: _jwt_service()

    if revocation_checker is not None:
        app.dependency_overrides[get_token_revocation_checker] = (
            lambda: revocation_checker
        )

    return app


def _make_client(
    *,
    jwt_service: JWTService | None = None,
    revocation_checker: Any = None,
) -> AsyncClient:
    app = _make_test_app(jwt_service=jwt_service, revocation_checker=revocation_checker)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _get_protected(
    client: AsyncClient,
    *,
    token: str | None = None,
    authorization: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    elif authorization is not None:
        headers["Authorization"] = authorization
    return await client.get("/protected", headers=headers)


async def _get_optional(
    client: AsyncClient,
    *,
    token: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return await client.get("/optional", headers=headers)


# ──────────────────────────────────────────────────────────────────────────── #
# AuthorizationContext creation                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestAuthorizationContextCreation:
    """AuthorizationContext is a frozen dataclass with all required fields."""

    def test_all_fields_accessible(self) -> None:
        now = datetime.now(UTC)
        ctx = AuthorizationContext(
            user_id=_USER_ID,
            session_id=_SESSION_ID,
            token_id=_JTI,
            token_version=1,
            session_version=1,
            authentication_method="password",
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            email=_EMAIL,
            is_email_verified=True,
        )
        assert ctx.user_id == _USER_ID
        assert ctx.session_id == _SESSION_ID
        assert ctx.token_id == _JTI
        assert ctx.token_version == 1
        assert ctx.session_version == 1
        assert ctx.authentication_method == "password"
        assert ctx.email == _EMAIL
        assert ctx.is_email_verified is True

    def test_frozen_raises_on_mutation(self) -> None:
        now = datetime.now(UTC)
        ctx = AuthorizationContext(
            user_id=_USER_ID,
            session_id=_SESSION_ID,
            token_id=_JTI,
            token_version=1,
            session_version=1,
            authentication_method="password",
            issued_at=now,
            expires_at=now + timedelta(minutes=15),
            email=_EMAIL,
            is_email_verified=True,
        )
        with pytest.raises((AttributeError, TypeError)):
            ctx.user_id = "other"  # type: ignore[misc]


# ──────────────────────────────────────────────────────────────────────────── #
# Valid token                                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class TestValidToken:
    """Valid Bearer token → 200 with populated AuthorizationContext."""

    async def test_status_200(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 200

    async def test_user_id_populated(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["user_id"] == _USER_ID

    async def test_session_id_populated(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["session_id"] == _SESSION_ID

    async def test_token_id_populated(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["token_id"] == _JTI

    async def test_email_populated(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["email"] == _EMAIL

    async def test_authentication_method_is_password(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["authentication_method"] == "password"

    async def test_is_email_verified_populated(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["is_email_verified"] is True


# ──────────────────────────────────────────────────────────────────────────── #
# Missing token                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestMissingToken:
    """Absent Authorization header → 401 AUTH_TOKEN_MISSING."""

    async def test_status_401(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert resp.status_code == 401

    async def test_error_code(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert resp.json()["error_code"] == "AUTH_TOKEN_MISSING"

    async def test_www_authenticate_header(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert resp.headers.get("www-authenticate") == "Bearer"

    async def test_rfc7807_type(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert "token-missing" in resp.json()["type"]


# ──────────────────────────────────────────────────────────────────────────── #
# Malformed header                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


class TestMalformedHeader:
    """Malformed Authorization header → 401 AUTH_TOKEN_MALFORMED."""

    async def test_wrong_scheme(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client, authorization="Token abc123")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_MALFORMED"

    async def test_bearer_no_space(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client, authorization="Bearertoken")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_MALFORMED"

    async def test_bearer_empty_value(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client, authorization="Bearer ")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_MALFORMED"

    async def test_bearer_only(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client, authorization="Bearer")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_MALFORMED"

    async def test_www_authenticate_header(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client, authorization="Token xyz")
        assert resp.headers.get("www-authenticate") == "Bearer"


# ──────────────────────────────────────────────────────────────────────────── #
# Expired token                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestExpiredToken:
    """Token past its exp claim → 401 AUTH_TOKEN_EXPIRED."""

    async def test_status_401(self) -> None:
        token = _expired_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 401

    async def test_error_code_expired(self) -> None:
        token = _expired_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["error_code"] == "AUTH_TOKEN_EXPIRED"

    async def test_rfc7807_type(self) -> None:
        token = _expired_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert "token-expired" in resp.json()["type"]

    async def test_www_authenticate_header(self) -> None:
        token = _expired_token()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.headers.get("www-authenticate") == "Bearer"


# ──────────────────────────────────────────────────────────────────────────── #
# Invalid signature                                                              #
# ──────────────────────────────────────────────────────────────────────────── #


class TestInvalidSignature:
    """Token signed with wrong key → 401 AUTH_TOKEN_INVALID."""

    async def test_status_401(self) -> None:
        token = _token_signed_with_wrong_key()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 401

    async def test_error_code_invalid(self) -> None:
        token = _token_signed_with_wrong_key()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["error_code"] == "AUTH_TOKEN_INVALID"

    async def test_not_expired_error_code(self) -> None:
        token = _token_signed_with_wrong_key()
        async with _make_client() as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["error_code"] != "AUTH_TOKEN_EXPIRED"

    async def test_garbage_string_yields_invalid(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client, token="not.a.jwt")
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_INVALID"


# ──────────────────────────────────────────────────────────────────────────── #
# Revoked token                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


class TestRevokedToken:
    """Valid token but JTI in revocation blacklist → 401 AUTH_TOKEN_REVOKED."""

    async def test_status_401(self) -> None:
        token = _valid_token()
        async with _make_client(revocation_checker=_AlwaysRevokedChecker()) as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 401

    async def test_error_code_revoked(self) -> None:
        token = _valid_token()
        async with _make_client(revocation_checker=_AlwaysRevokedChecker()) as client:
            resp = await _get_protected(client, token=token)
        assert resp.json()["error_code"] == "AUTH_TOKEN_REVOKED"

    async def test_rfc7807_type(self) -> None:
        token = _valid_token()
        async with _make_client(revocation_checker=_AlwaysRevokedChecker()) as client:
            resp = await _get_protected(client, token=token)
        assert "token-revoked" in resp.json()["type"]

    async def test_null_checker_does_not_revoke(self) -> None:
        token = _valid_token()
        async with _make_client(revocation_checker=NullTokenRevocationChecker()) as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────────── #
# Optional authentication                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


class TestOptionalAuthentication:
    """OptionalAuthentication returns None on missing, context on valid, 401 on invalid."""

    async def test_no_token_returns_null(self) -> None:
        async with _make_client() as client:
            resp = await _get_optional(client)
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is False

    async def test_valid_token_returns_context(self) -> None:
        token = _valid_token()
        async with _make_client() as client:
            resp = await _get_optional(client, token=token)
        assert resp.status_code == 200
        assert resp.json()["authenticated"] is True
        assert resp.json()["user_id"] == _USER_ID

    async def test_malformed_token_yields_401(self) -> None:
        async with _make_client() as client:
            resp = await client.get(
                "/optional",
                headers={"Authorization": "Token xyz"},
            )
        assert resp.status_code == 401

    async def test_expired_token_yields_401(self) -> None:
        token = _expired_token()
        async with _make_client() as client:
            resp = await _get_optional(client, token=token)
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_EXPIRED"


# ──────────────────────────────────────────────────────────────────────────── #
# Dependency injection                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


class TestDependencyInjection:
    """Verify that dependency_overrides reach the authorization logic."""

    async def test_jwt_service_override_used(self) -> None:
        real_svc = _jwt_service()
        token = real_svc.create_access_token(_claims())
        async with _make_client(jwt_service=real_svc) as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 200

    async def test_revocation_checker_override_used(self) -> None:
        token = _valid_token()
        revoked = _AlwaysRevokedChecker()
        async with _make_client(revocation_checker=revoked) as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 401
        assert resp.json()["error_code"] == "AUTH_TOKEN_REVOKED"

    async def test_null_revocation_checker_passes_valid_token(self) -> None:
        token = _valid_token()
        async with _make_client(revocation_checker=NullTokenRevocationChecker()) as client:
            resp = await _get_protected(client, token=token)
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────────────── #
# RFC 7807 error response format                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


class TestErrorResponseFormat:
    """All error responses include required RFC 7807 fields."""

    @pytest.mark.parametrize(
        "scenario",
        [
            ("no_header", None, None),
            ("bad_scheme", None, "Token abc"),
            ("expired", "expired", None),
            ("wrong_key", "wrong_key", None),
        ],
    )
    async def test_rfc7807_fields_present(self, scenario: tuple[str, Any, Any]) -> None:
        label, token_type, auth_header = scenario
        token: str | None = None
        if token_type == "expired":
            token = _expired_token()
        elif token_type == "wrong_key":
            token = _token_signed_with_wrong_key()

        async with _make_client() as client:
            resp = await _get_protected(
                client,
                token=token,
                authorization=auth_header,
            )

        body = resp.json()
        for field in ("type", "title", "status", "detail", "instance", "error_code", "trace_id"):
            assert field in body, f"[{label}] Missing RFC 7807 field: {field}"

    async def test_instance_is_request_path(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert resp.json()["instance"] == "/protected"

    async def test_status_field_matches_http_status(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert resp.json()["status"] == resp.status_code

    async def test_type_uses_travix_error_base(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        assert resp.json()["type"].startswith("https://errors.travix.ai/auth/")

    async def test_trace_id_present(self) -> None:
        async with _make_client() as client:
            resp = await _get_protected(client)
        trace_id = resp.json()["trace_id"]
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0
