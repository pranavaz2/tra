"""Provider-neutral maps and places service interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class GeocodedPlace:
    """A provider-neutral geocoded place result."""

    name: str
    country_code: str
    latitude: float
    longitude: float
    region: str | None = None
    locality: str | None = None
    provider_place_id: str | None = None


@dataclass(frozen=True)
class PlaceDetails:
    """Detailed real-world place information resolved from a Places provider."""

    provider_place_id: str
    name: str
    formatted_address: str
    latitude: float
    longitude: float
    country_code: str | None = None
    region: str | None = None
    locality: str | None = None
    types: list[str] = field(default_factory=list)
    rating: float | None = None
    user_ratings_total: int | None = None
    opening_hours: list[str] = field(default_factory=list)
    is_open_now: bool | None = None


@dataclass(frozen=True)
class PlacePrediction:
    """Autocomplete candidate prediction from a Places provider."""

    provider_place_id: str
    description: str
    primary_text: str
    secondary_text: str | None = None
    types: list[str] = field(default_factory=list)


@runtime_checkable
class MapsProvider(Protocol):
    """Abstract geocoding provider contract."""

    async def geocode(self, query: str) -> list[GeocodedPlace]:
        """Return provider-neutral geocoding results for a user query."""
        ...


@runtime_checkable
class PlacesProvider(Protocol):
    """
    Abstract Places provider contract.

    Supports search, resolution, autocomplete, and nearby exploration for
    verified real-world places.
    """

    async def text_search(
        self,
        query: str,
        *,
        location: tuple[float, float] | None = None,
        radius_meters: int | None = None,
    ) -> list[PlaceDetails]:
        """Search places by text query with optional spatial bias."""
        ...

    async def autocomplete(
        self,
        input_text: str,
        *,
        location: tuple[float, float] | None = None,
        radius_meters: int | None = None,
    ) -> list[PlacePrediction]:
        """Return place predictions for an incomplete text query."""
        ...

    async def get_place_details(self, place_id: str) -> PlaceDetails | None:
        """Fetch full details for a verified provider place ID."""
        ...

    async def nearby_search(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_meters: int,
        place_type: str | None = None,
    ) -> list[PlaceDetails]:
        """Search places around geographic coordinates within radius."""
        ...

    async def geocode(self, query: str) -> list[GeocodedPlace]:
        """Geocode query string into coordinates and locality."""
        ...
