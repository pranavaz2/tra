"""
Production Google Places and Maps provider implementation.

Queries Google Places Web Service APIs (Text Search, Details, Autocomplete, Nearby, Geocode)
using an async HTTP client with retries, timeouts, error mapping, and caching.
"""

from __future__ import annotations

import asyncio
import json
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

_BASE_URL = "https://maps.googleapis.com/maps/api"


class GooglePlacesProvider(PlacesProvider, MapsProvider):
    """Production Places and Geocoding provider backed by Google Maps APIs."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        cache_client: Any | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Google Places API key cannot be empty.")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._cache = cache_client
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        elif getattr(self._client, "is_closed", False) is True:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def _execute_with_retry(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute GET request with timeout and exponential backoff retries."""
        params_with_key = {**params, "key": self._api_key}
        client = await self._get_client()

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.get(url, params=params_with_key)
                if response.status_code == 429:
                    raise ExternalServiceError(
                        "google_places", "Google Places rate limit exceeded (HTTP 429)."
                    )
                if response.status_code >= 500:
                    response.raise_for_status()

                data = response.json()
                status = data.get("status")

                if status in ("OK", "ZERO_RESULTS"):
                    return data
                if status == "OVER_QUERY_LIMIT":
                    raise ExternalServiceError(
                        "google_places", "Google Places quota or query limit exceeded."
                    )
                if status == "REQUEST_DENIED":
                    error_msg = data.get("error_message", "Request denied by Google Places API.")
                    logger.error("Google Places authentication denied: %s", error_msg)
                    raise ExternalServiceError(
                        "google_places", "Google Places API authentication or permissions failed."
                    )
                if status == "INVALID_REQUEST":
                    logger.warning(
                        "Invalid request to Google Places API: %s", data.get("error_message")
                    )
                    return data

                # Unknown status
                raise ExternalServiceError(
                    "google_places", f"Google Places returned unexpected status: {status}"
                )

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == self._max_retries:
                    break
                await asyncio.sleep(0.3 * (2 ** (attempt - 1)))

        logger.error(
            "Google Places request failed after %d retries: %s", self._max_retries, last_exc
        )
        raise ExternalServiceError(
            "google_places", "Google Places API is currently unavailable.", cause=last_exc
        )

    def _parse_address_components(
        self, components: list[dict[str, Any]]
    ) -> tuple[str | None, str | None, str | None]:
        """Extract country_code, region, locality from Google address components."""
        country_code: str | None = None
        region: str | None = None
        locality: str | None = None

        for comp in components:
            types = comp.get("types", [])
            if "country" in types:
                country_code = comp.get("short_name")
            elif "administrative_area_level_1" in types:
                region = comp.get("long_name")
            elif "locality" in types:
                locality = comp.get("long_name")
            elif "postal_town" in types and locality is None:
                locality = comp.get("long_name")

        return country_code, region, locality

    def _parse_place_details(self, raw: dict[str, Any]) -> PlaceDetails | None:
        """Parse raw Google Places object into domain PlaceDetails."""
        place_id = raw.get("place_id")
        name = raw.get("name")
        geometry = raw.get("geometry", {})
        location = geometry.get("location", {})
        lat = location.get("lat")
        lng = location.get("lng")

        if not place_id or not name or lat is None or lng is None:
            return None

        components = raw.get("address_components", [])
        country_code, region, locality = self._parse_address_components(components)

        opening_hours_data = raw.get("opening_hours", {})
        weekday_text = opening_hours_data.get("weekday_text", [])
        is_open_now = opening_hours_data.get("open_now")

        rating = raw.get("rating")
        rating_float = float(rating) if rating is not None else None

        user_ratings_total = raw.get("user_ratings_total")

        return PlaceDetails(
            provider_place_id=str(place_id),
            name=str(name),
            formatted_address=str(raw.get("formatted_address") or raw.get("vicinity") or name),
            latitude=float(lat),
            longitude=float(lng),
            country_code=country_code,
            region=region,
            locality=locality,
            types=raw.get("types", []),
            rating=rating_float,
            user_ratings_total=int(user_ratings_total) if user_ratings_total is not None else None,
            opening_hours=list(weekday_text),
            is_open_now=bool(is_open_now) if is_open_now is not None else None,
        )

    async def text_search(
        self,
        query: str,
        *,
        location: tuple[float, float] | None = None,
        radius_meters: int | None = None,
    ) -> list[PlaceDetails]:
        """Search places by text query."""
        clean_query = query.strip()
        if not clean_query:
            return []

        # Check cache if available
        cache_key = f"places:text:{clean_query}:{location}:{radius_meters}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    items = json.loads(cached)
                    return [PlaceDetails(**item) for item in items]
            except Exception as e:
                logger.debug("Places cache read error: %s", e)

        url = f"{_BASE_URL}/place/textsearch/json"
        params: dict[str, Any] = {"query": clean_query}
        if location and radius_meters:
            params["location"] = f"{location[0]},{location[1]}"
            params["radius"] = radius_meters

        data = await self._execute_with_retry(url, params)
        raw_results = data.get("results", [])

        results: list[PlaceDetails] = []
        for r in raw_results:
            details = self._parse_place_details(r)
            if details:
                results.append(details)

        if self._cache and results:
            try:
                await self._cache.set(
                    cache_key,
                    json.dumps([d.__dict__ for d in results]),
                    ttl=3600,
                )
            except Exception as e:
                logger.debug("Places cache write error: %s", e)

        return results

    async def autocomplete(
        self,
        input_text: str,
        *,
        location: tuple[float, float] | None = None,
        radius_meters: int | None = None,
    ) -> list[PlacePrediction]:
        """Return autocomplete suggestions for a prefix."""
        clean_input = input_text.strip()
        if not clean_input:
            return []

        url = f"{_BASE_URL}/place/autocomplete/json"
        params: dict[str, Any] = {"input": clean_input}
        if location and radius_meters:
            params["location"] = f"{location[0]},{location[1]}"
            params["radius"] = radius_meters

        data = await self._execute_with_retry(url, params)
        predictions = data.get("predictions", [])

        results: list[PlacePrediction] = []
        for p in predictions:
            place_id = p.get("place_id")
            description = p.get("description", "")
            sf = p.get("structured_formatting", {})
            primary = sf.get("main_text") or description
            secondary = sf.get("secondary_text")
            types = p.get("types", [])

            if place_id:
                results.append(
                    PlacePrediction(
                        provider_place_id=str(place_id),
                        description=str(description),
                        primary_text=str(primary),
                        secondary_text=str(secondary) if secondary else None,
                        types=list(types),
                    )
                )

        return results

    async def get_place_details(self, place_id: str) -> PlaceDetails | None:
        """Fetch place details for a given place_id."""
        clean_id = place_id.strip()
        if not clean_id:
            return None

        cache_key = f"places:details:{clean_id}"
        if self._cache:
            try:
                cached = await self._cache.get(cache_key)
                if cached:
                    return PlaceDetails(**json.loads(cached))
            except Exception as e:
                logger.debug("Place details cache read error: %s", e)

        url = f"{_BASE_URL}/place/details/json"
        params = {"place_id": clean_id}
        data = await self._execute_with_retry(url, params)
        raw_result = data.get("result")
        if not raw_result:
            return None

        details = self._parse_place_details(raw_result)
        if details and self._cache:
            try:
                await self._cache.set(cache_key, json.dumps(details.__dict__), ttl=86400)
            except Exception as e:
                logger.debug("Place details cache write error: %s", e)

        return details

    async def nearby_search(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_meters: int,
        place_type: str | None = None,
    ) -> list[PlaceDetails]:
        """Search nearby places within radius."""
        url = f"{_BASE_URL}/place/nearbysearch/json"
        params: dict[str, Any] = {
            "location": f"{latitude},{longitude}",
            "radius": radius_meters,
        }
        if place_type:
            params["type"] = place_type

        data = await self._execute_with_retry(url, params)
        raw_results = data.get("results", [])

        results: list[PlaceDetails] = []
        for r in raw_results:
            details = self._parse_place_details(r)
            if details:
                results.append(details)
        return results

    async def geocode(self, query: str) -> list[GeocodedPlace]:
        """Geocode address/place query into coordinates."""
        clean_query = query.strip()
        if not clean_query:
            return []

        url = f"{_BASE_URL}/geocode/json"
        data = await self._execute_with_retry(url, {"address": clean_query})
        raw_results = data.get("results", [])

        results: list[GeocodedPlace] = []
        for r in raw_results:
            geometry = r.get("geometry", {})
            loc = geometry.get("location", {})
            lat = loc.get("lat")
            lng = loc.get("lng")
            if lat is None or lng is None:
                continue

            components = r.get("address_components", [])
            country_code, region, locality = self._parse_address_components(components)

            results.append(
                GeocodedPlace(
                    name=r.get("formatted_address") or clean_query,
                    country_code=country_code or "US",
                    latitude=float(lat),
                    longitude=float(lng),
                    region=region,
                    locality=locality,
                    provider_place_id=r.get("place_id"),
                )
            )

        return results
