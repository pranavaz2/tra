"""Mock maps provider for local development and tests."""

from __future__ import annotations

from app.services.maps.base import GeocodedPlace, MapsProvider


class MockMapsProvider(MapsProvider):
    """Deterministic maps provider that never calls external services."""

    async def geocode(self, query: str) -> list[GeocodedPlace]:
        """Return an empty result set for all queries."""
        return []
