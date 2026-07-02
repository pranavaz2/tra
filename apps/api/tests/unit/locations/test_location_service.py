"""Unit tests for the locations service."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.modules.locations.exceptions import InvalidLocationQueryError, LocationNotFoundError
from app.modules.locations.models import LocationType
from app.modules.locations.service import LocationService


class StubRepository:
    """Minimal repository test double."""

    def __init__(self) -> None:
        self.location = object()
        self.received_query: str | None = None

    async def get_by_id(self, location_id: uuid.UUID) -> object | None:
        return self.location

    async def get_by_slug(self, slug: str) -> object | None:
        return self.location

    async def search(
        self,
        *,
        query: str | None = None,
        country_code: str | None = None,
        location_type: LocationType | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[object], str | None]:
        self.received_query = query
        return [self.location], None

    async def find_nearby(
        self,
        *,
        latitude: Decimal,
        longitude: Decimal,
        radius_meters: int,
        limit: int = 20,
    ) -> list[object]:
        return [self.location]


class MissingRepository(StubRepository):
    """Repository test double that returns no records."""

    async def get_by_id(self, location_id: uuid.UUID) -> object | None:
        return None

    async def get_by_slug(self, slug: str) -> object | None:
        return None


async def test_get_location_returns_repository_location() -> None:
    repo = StubRepository()
    service = LocationService(repo)  # type: ignore[arg-type]

    result = await service.get_location(uuid.uuid4())

    assert result is repo.location


async def test_get_location_raises_when_missing() -> None:
    service = LocationService(MissingRepository())  # type: ignore[arg-type]

    with pytest.raises(LocationNotFoundError):
        await service.get_location(uuid.uuid4())


async def test_get_location_by_slug_raises_when_missing() -> None:
    service = LocationService(MissingRepository())  # type: ignore[arg-type]

    with pytest.raises(LocationNotFoundError):
        await service.get_location_by_slug("missing")


async def test_search_locations_strips_query() -> None:
    repo = StubRepository()
    service = LocationService(repo)  # type: ignore[arg-type]

    await service.search_locations(query="  paris  ")

    assert repo.received_query == "paris"


async def test_search_locations_rejects_empty_query() -> None:
    service = LocationService(StubRepository())  # type: ignore[arg-type]

    with pytest.raises(InvalidLocationQueryError):
        await service.search_locations(query="   ")


async def test_find_nearby_locations_returns_repository_results() -> None:
    repo = StubRepository()
    service = LocationService(repo)  # type: ignore[arg-type]

    result = await service.find_nearby_locations(
        latitude=Decimal("48.8566"),
        longitude=Decimal("2.3522"),
        radius_meters=1000,
    )

    assert result == [repo.location]
