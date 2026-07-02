"""FastAPI router for authenticated location read endpoints."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from app.core.security.auth.dependencies import RequireAuthentication
from app.dependencies import DatabaseSession
from app.modules.locations.exceptions import InvalidLocationQueryError, LocationNotFoundError
from app.modules.locations.models import LocationType
from app.modules.locations.repository import LocationRepository
from app.modules.locations.schemas import DataEnvelope, LocationListResponse, LocationResponse
from app.modules.locations.service import LocationService

router = APIRouter(prefix="/locations", tags=["Locations"])


def get_location_repository(session: DatabaseSession) -> LocationRepository:
    """Build the locations repository for the current request."""
    return LocationRepository(session)


CurrentLocationRepository = Annotated[
    LocationRepository, Depends(get_location_repository)
]


def get_location_service(repository: CurrentLocationRepository) -> LocationService:
    """Build the locations service for the current request."""
    return LocationService(repository)


CurrentLocationService = Annotated[LocationService, Depends(get_location_service)]


def _problem_response(
    *,
    status_code: int,
    slug: str,
    title: str,
    detail: str,
    instance: str,
    error_code: str,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": f"https://errors.travix.ai/locations/{slug}",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": instance,
            "error_code": error_code,
        },
    )


@router.get("", response_model=DataEnvelope[LocationListResponse])
async def list_locations(
    auth: RequireAuthentication,
    service: CurrentLocationService,
    query: Annotated[str | None, Query(max_length=255)] = None,
    country_code: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    location_type: LocationType | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DataEnvelope[LocationListResponse] | JSONResponse:
    """Search canonical locations."""
    try:
        locations, next_cursor = await service.search_locations(
            query=query,
            country_code=country_code,
            location_type=location_type,
            cursor=cursor,
            limit=limit,
        )
    except InvalidLocationQueryError:
        return _problem_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            slug="invalid-location-query",
            title="Invalid Location Query",
            detail="Location query must not be empty.",
            instance="/api/v1/locations",
            error_code="LOCATION_QUERY_INVALID",
        )

    return DataEnvelope(
        data=LocationListResponse(
            items=[LocationResponse.model_validate(location) for location in locations],
            next_cursor=next_cursor,
            limit=limit,
        )
    )


@router.get("/nearby", response_model=DataEnvelope[LocationListResponse])
async def list_nearby_locations(
    auth: RequireAuthentication,
    service: CurrentLocationService,
    latitude: Annotated[Decimal, Query(ge=Decimal("-90"), le=Decimal("90"))],
    longitude: Annotated[Decimal, Query(ge=Decimal("-180"), le=Decimal("180"))],
    radius_meters: Annotated[int, Query(ge=1, le=100000)] = 50000,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DataEnvelope[LocationListResponse]:
    """Return locations near a coordinate."""
    locations = await service.find_nearby_locations(
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        limit=limit,
    )
    return DataEnvelope(
        data=LocationListResponse(
            items=[LocationResponse.model_validate(location) for location in locations],
            next_cursor=None,
            limit=limit,
        )
    )


@router.get("/slug/{slug}", response_model=DataEnvelope[LocationResponse])
async def get_location_by_slug(
    auth: RequireAuthentication,
    service: CurrentLocationService,
    slug: str,
) -> DataEnvelope[LocationResponse] | JSONResponse:
    """Return one canonical location by slug."""
    try:
        location = await service.get_location_by_slug(slug)
    except LocationNotFoundError:
        return _problem_response(
            status_code=status.HTTP_404_NOT_FOUND,
            slug="location-not-found",
            title="Location Not Found",
            detail="Location was not found.",
            instance=f"/api/v1/locations/slug/{slug}",
            error_code="LOCATION_NOT_FOUND",
        )
    return DataEnvelope(data=LocationResponse.model_validate(location))


@router.get("/{location_id}", response_model=DataEnvelope[LocationResponse])
async def get_location(
    auth: RequireAuthentication,
    service: CurrentLocationService,
    location_id: UUID,
) -> DataEnvelope[LocationResponse] | JSONResponse:
    """Return one canonical location by ID."""
    try:
        location = await service.get_location(location_id)
    except LocationNotFoundError:
        return _problem_response(
            status_code=status.HTTP_404_NOT_FOUND,
            slug="location-not-found",
            title="Location Not Found",
            detail="Location was not found.",
            instance=f"/api/v1/locations/{location_id}",
            error_code="LOCATION_NOT_FOUND",
        )
    return DataEnvelope(data=LocationResponse.model_validate(location))
