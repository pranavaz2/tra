"""Async repository for location persistence and lookup."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.locations.models import Location, LocationType


@dataclass(frozen=True, kw_only=True)
class LocationCreate:
    """Data required to create a canonical location."""

    name: str
    slug: str
    location_type: LocationType
    country_code: str
    latitude: Decimal
    longitude: Decimal
    region: str | None = None
    locality: str | None = None
    provider_place_id: str | None = None
    description: str | None = None


class LocationRepository:
    """SQLAlchemy-backed repository for locations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, data: LocationCreate) -> Location:
        """Persist a new location and return the ORM model."""
        location = Location(
            name=data.name,
            slug=data.slug,
            location_type=data.location_type,
            country_code=data.country_code.upper(),
            region=data.region,
            locality=data.locality,
            latitude=data.latitude,
            longitude=data.longitude,
            point=func.ST_SetSRID(func.ST_MakePoint(data.longitude, data.latitude), 4326),
            provider_place_id=data.provider_place_id,
            description=data.description,
        )
        self._session.add(location)
        await self._session.flush([location])
        await self._session.refresh(location)
        return location

    async def get_by_id(self, location_id: UUID) -> Location | None:
        """Return an active location by ID, or None."""
        stmt = _exclude_deleted(select(Location).where(Location.id == location_id))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Location | None:
        """Return an active location by slug, or None."""
        stmt = _exclude_deleted(select(Location).where(Location.slug == slug))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        *,
        query: str | None = None,
        country_code: str | None = None,
        location_type: LocationType | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[Location], str | None]:
        """Search active locations using cursor pagination."""
        stmt = self._base_search_query(
            query=query,
            country_code=country_code,
            location_type=location_type,
        )

        if cursor is not None:
            stmt = stmt.where(Location.name > _decode_cursor(cursor))

        stmt = stmt.order_by(Location.name.asc(), Location.id.asc()).limit(limit + 1)
        result = await self._session.execute(stmt)
        rows = list(result.scalars())

        next_cursor: str | None = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = _encode_cursor(rows[-1].name)

        return rows, next_cursor

    async def find_nearby(
        self,
        *,
        latitude: Decimal,
        longitude: Decimal,
        radius_meters: int,
        limit: int = 20,
    ) -> list[Location]:
        """Return active locations within a radius, ordered by distance."""
        point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
        stmt = _exclude_deleted(select(Location)).where(
            func.ST_DWithin(func.Geography(Location.point), func.Geography(point), radius_meters)
        )
        stmt = stmt.order_by(func.ST_DistanceSphere(Location.point, point)).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def soft_delete(self, location_id: UUID) -> bool:
        """Soft-delete a location. Returns True when a row was changed."""
        stmt = (
            update(Location)
            .where(Location.id == location_id, Location.deleted_at.is_(None))
            .values(deleted_at=func.now())
        )
        result = await self._session.execute(stmt)
        return result.rowcount == 1

    def _base_search_query(
        self,
        *,
        query: str | None,
        country_code: str | None,
        location_type: LocationType | None,
    ) -> Select[tuple[Location]]:
        stmt = _exclude_deleted(select(Location))

        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Location.name.ilike(pattern),
                    Location.region.ilike(pattern),
                    Location.locality.ilike(pattern),
                )
            )

        if country_code:
            stmt = stmt.where(Location.country_code == country_code.upper())

        if location_type is not None:
            stmt = stmt.where(Location.location_type == location_type.value)

        return stmt


def _exclude_deleted(query: Select[tuple[Location]]) -> Select[tuple[Location]]:
    """Apply the locations module soft-delete filter."""
    return query.where(Location.deleted_at.is_(None))


def _encode_cursor(value: str) -> str:
    """Encode a cursor value without importing shared pagination."""
    return base64.urlsafe_b64encode(value.encode()).decode()


def _decode_cursor(cursor: str) -> str:
    """Decode a cursor value without importing shared pagination."""
    return base64.urlsafe_b64decode(cursor.encode()).decode()
