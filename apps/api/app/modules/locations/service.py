"""Application service for location lookup workflows."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.modules.locations.exceptions import InvalidLocationQueryError, LocationNotFoundError
from app.modules.locations.models import Location, LocationType
from app.modules.locations.repository import LocationRepository


class LocationService:
    """Business orchestration for canonical location lookups."""

    def __init__(self, repository: LocationRepository) -> None:
        self._repository = repository

    async def get_location(self, location_id: UUID) -> Location:
        """Return a location by ID or raise a module error."""
        location = await self._repository.get_by_id(location_id)
        if location is None:
            raise LocationNotFoundError(str(location_id))
        return location

    async def get_location_by_slug(self, slug: str) -> Location:
        """Return a location by slug or raise a module error."""
        location = await self._repository.get_by_slug(slug)
        if location is None:
            raise LocationNotFoundError(slug)
        return location

    async def search_locations(
        self,
        *,
        query: str | None = None,
        country_code: str | None = None,
        location_type: LocationType | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[Location], str | None]:
        """Search locations with optional filters."""
        normalized_query = query.strip() if query is not None else None
        if normalized_query == "":
            raise InvalidLocationQueryError()

        return await self._repository.search(
            query=normalized_query,
            country_code=country_code,
            location_type=location_type,
            cursor=cursor,
            limit=limit,
        )

    async def find_nearby_locations(
        self,
        *,
        latitude: Decimal,
        longitude: Decimal,
        radius_meters: int,
        limit: int = 20,
    ) -> list[Location]:
        """Find nearby canonical locations."""
        return await self._repository.find_nearby(
            latitude=latitude,
            longitude=longitude,
            radius_meters=radius_meters,
            limit=limit,
        )
