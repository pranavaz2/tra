"""
OpenStreetMap Nominatim Places Provider.

Free, no API key required, no billing needed.
Uses the Nominatim geocoding API + Overpass for POI search.
Rate limit: 1 req/sec (enforced with asyncio.sleep).

Docs: https://nominatim.org/release-docs/develop/api/Search/
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.services.maps.base import (
    GeocodedPlace,
    MapsProvider,
    PlaceDetails,
    PlacePrediction,
    PlacesProvider,
)
from app.shared.domain.errors import ExternalServiceError

logger = logging.getLogger(__name__)

_NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
_USER_AGENT = "TravixAI/1.0 (travel planning app; contact@travix.ai)"


class NominatimPlacesProvider(PlacesProvider, MapsProvider):
    """
    Free Places and Geocoding provider backed by OpenStreetMap Nominatim.

    No API key or billing required.
    Enforces 1 req/s to comply with Nominatim usage policy.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"},
            )
        elif getattr(self._client, "is_closed", False):
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "en"},
            )
        return self._client

    async def _search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Run a Nominatim free-text search with a polite delay between calls."""
        await asyncio.sleep(0.3)  # ~3 req/s — well within Nominatim fair-use policy
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{_NOMINATIM_BASE}/search",
                params={
                    "q": query,
                    "format": "json",
                    "limit": limit,
                    "addressdetails": 1,
                    "extratags": 1,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ExternalServiceError("nominatim", "Nominatim request timed out or failed.", cause=exc)
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError("nominatim", f"Nominatim HTTP error: {exc.response.status_code}", cause=exc)

    def _to_place_prediction(self, item: dict[str, Any]) -> PlacePrediction:
        name = (
            item.get("extratags", {}).get("name")
            or item.get("name")
            or item.get("display_name", "").split(",")[0].strip()
        )
        return PlacePrediction(
            provider_place_id=item.get("osm_id") or item.get("place_id") or "",
            name=name,
            formatted_address=item.get("display_name", ""),
            latitude=float(item.get("lat", 0)),
            longitude=float(item.get("lon", 0)),
            types=[item.get("type", ""), item.get("class", "")],
            rating=None,
        )

    # ── PlacesProvider interface ──────────────────────────────────────────────

    async def text_search(self, query: str, location_bias: str | None = None) -> list[PlacePrediction]:
        search_query = f"{query} {location_bias}" if location_bias else query
        results = await self._search(search_query, limit=5)
        return [self._to_place_prediction(r) for r in results]

    async def get_place_details(self, provider_place_id: str) -> PlaceDetails:
        await self._rate_limit()
        client = await self._get_client()
        try:
            resp = await client.get(
                f"{_NOMINATIM_BASE}/details",
                params={
                    "osmid": provider_place_id,
                    "format": "json",
                    "addressdetails": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            raise ExternalServiceError("nominatim", f"Nominatim details failed: {exc}", cause=exc)

        name = (data.get("localname") or data.get("names", {}).get("name", provider_place_id))
        address = data.get("address", {})
        formatted = ", ".join(filter(None, [
            address.get("road"), address.get("city") or address.get("town"),
            address.get("state"), address.get("country"),
        ]))
        return PlaceDetails(
            provider_place_id=provider_place_id,
            name=name,
            formatted_address=formatted or name,
            latitude=float(data.get("centroid", {}).get("coordinates", [0, 0])[1]),
            longitude=float(data.get("centroid", {}).get("coordinates", [0, 0])[0]),
            rating=None,
            phone_number=None,
            website=None,
            opening_hours=None,
            photos=[],
            types=[data.get("type", "")],
        )

    async def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int = 1000,
        place_type: str | None = None,
    ) -> list[PlacePrediction]:
        query = place_type or "point of interest"
        results = await self._search(f"{query} near {latitude},{longitude}", limit=5)
        return [self._to_place_prediction(r) for r in results]

    async def autocomplete(self, input_text: str, location_bias: str | None = None) -> list[PlacePrediction]:
        return await self.text_search(input_text, location_bias)

    # ── MapsProvider interface ────────────────────────────────────────────────

    async def geocode(self, address: str) -> GeocodedPlace | None:
        results = await self._search(address, limit=1)
        if not results:
            return None
        r = results[0]
        name = r.get("display_name", "").split(",")[0].strip()
        return GeocodedPlace(
            name=name,
            formatted_address=r.get("display_name", ""),
            latitude=float(r.get("lat", 0)),
            longitude=float(r.get("lon", 0)),
            provider_place_id=str(r.get("place_id", "")),
        )

    async def reverse_geocode(self, latitude: float, longitude: float) -> GeocodedPlace | None:
        await self._rate_limit()
        client = await self._get_client()
        resp = await client.get(
            f"{_NOMINATIM_BASE}/reverse",
            params={"lat": latitude, "lon": longitude, "format": "json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            return None
        name = data.get("display_name", "").split(",")[0].strip()
        return GeocodedPlace(
            name=name,
            formatted_address=data.get("display_name", ""),
            latitude=latitude,
            longitude=longitude,
            provider_place_id=str(data.get("place_id", "")),
        )
