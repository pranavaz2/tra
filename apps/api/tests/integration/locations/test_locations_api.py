"""Integration tests for the locations API surface."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import FastAPI
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.core.security.auth.errors import AuthorizationError
from app.modules.locations.exceptions import LocationNotFoundError
from app.modules.locations.models import LocationType
from app.modules.locations.router import get_location_service, router


class LocationStub:
    """Object with the attributes required by LocationResponse."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        self.id = uuid.uuid4()
        self.name = "Paris"
        self.slug = "paris-fr"
        self.location_type = LocationType.CITY
        self.country_code = "FR"
        self.region = "Ile-de-France"
        self.locality = "Paris"
        self.latitude = Decimal("48.856600")
        self.longitude = Decimal("2.352200")
        self.provider_place_id = None
        self.description = None
        self.created_at = now
        self.updated_at = now


class StubLocationService:
    """Location service test double for API integration tests."""

    def __init__(self, *, missing: bool = False) -> None:
        self._missing = missing
        self.location = LocationStub()

    async def search_locations(self, **kwargs: Any) -> tuple[list[LocationStub], str | None]:
        return [self.location], None

    async def find_nearby_locations(self, **kwargs: Any) -> list[LocationStub]:
        return [self.location]

    async def get_location(self, location_id: uuid.UUID) -> LocationStub:
        if self._missing:
            raise LocationNotFoundError(str(location_id))
        return self.location

    async def get_location_by_slug(self, slug: str) -> LocationStub:
        if self._missing:
            raise LocationNotFoundError(slug)
        return self.location


def _auth_context() -> AuthorizationContext:
    now = datetime.now(UTC)
    return AuthorizationContext(
        user_id=str(uuid.uuid4()),
        session_id=str(uuid.uuid4()),
        token_id=str(uuid.uuid4()),
        token_version=1,
        session_version=1,
        authentication_method="password",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        email="user@example.com",
        is_email_verified=True,
    )


def _make_app(service: StubLocationService) -> FastAPI:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(router)
    app.include_router(api_v1)
    app.dependency_overrides[get_location_service] = lambda: service
    app.dependency_overrides[get_authorization_context] = _auth_context
    return app


async def _authorization_error_handler(
    request: object,
    exc: AuthorizationError,
) -> object:
    return exc.to_response()


async def test_list_locations_returns_data_envelope() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(StubLocationService())),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/api/v1/locations", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["slug"] == "paris-fr"


async def test_get_location_requires_authentication_without_override() -> None:
    app = FastAPI()
    app.add_exception_handler(AuthorizationError, _authorization_error_handler)  # type: ignore[arg-type]
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(router)
    app.include_router(api_v1)
    app.dependency_overrides[get_location_service] = lambda: StubLocationService()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(f"/api/v1/locations/{uuid.uuid4()}")

    assert response.status_code == 401
    assert response.json()["type"].endswith("/token-missing")


async def test_get_location_not_found_returns_problem_details() -> None:
    location_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=_make_app(StubLocationService(missing=True))),
        base_url="http://testserver",
    ) as client:
        response = await client.get(
            f"/api/v1/locations/{location_id}",
            headers={"Authorization": "Bearer token"},
        )

    body = response.json()
    assert response.status_code == 404
    assert body["type"].endswith("/location-not-found")
    assert body["status"] == 404
    assert body["instance"] == f"/api/v1/locations/{location_id}"
