"""Pydantic schemas for the locations API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.locations.models import LocationType

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    """Standard single-resource success envelope."""

    model_config = ConfigDict(populate_by_name=True)

    data: T


class LocationResponse(BaseModel):
    """Location response returned by all locations endpoints."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    name: str
    slug: str
    location_type: LocationType
    country_code: str
    region: str | None
    locality: str | None
    latitude: Decimal
    longitude: Decimal
    provider_place_id: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class LocationListResponse(BaseModel):
    """Paginated list of locations."""

    model_config = ConfigDict(populate_by_name=True)

    items: list[LocationResponse]
    next_cursor: str | None = None
    limit: int = Field(ge=1, le=100)


class LocationSearchQuery(BaseModel):
    """Validated location search query parameters."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str | None = Field(default=None, max_length=255)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    location_type: LocationType | None = None
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
