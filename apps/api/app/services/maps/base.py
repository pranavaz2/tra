"""Provider-neutral maps service interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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


class MapsProvider(Protocol):
    """Abstract maps/geocoding provider contract."""

    async def geocode(self, query: str) -> list[GeocodedPlace]:
        """Return provider-neutral geocoding results for a user query."""
        ...
