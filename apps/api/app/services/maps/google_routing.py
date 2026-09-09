"""
Production Google Directions / Routing provider implementation.

Calculates real route distances and travel durations using Google Directions API
with async HTTP, exponential backoff retries, rate-limit handling, and Redis/in-memory caching.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from app.services.maps.route import RouteDetails, RoutingProvider, TravelMode
from app.shared.domain.errors import ExternalServiceError

logger = logging.getLogger(__name__)

_DIRECTIONS_BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"

_GOOGLE_MODE_MAP = {
    TravelMode.DRIVE.value: "driving",
    TravelMode.WALK.value: "walking",
    TravelMode.BICYCLE.value: "bicycling",
    TravelMode.TRANSIT.value: "transit",
    "driving": "driving",
    "walking": "walking",
    "bicycling": "bicycling",
    "transit": "transit",
}


class GoogleRoutingProvider(RoutingProvider):
    """Production Routing Provider backed by Google Maps Directions API."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        cache_client: Any | None = None,
        cache_ttl_seconds: int = 86400,  # 24 hours
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Google Maps API key cannot be empty.")
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._cache = cache_client
        self._cache_ttl = cache_ttl_seconds
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        elif getattr(self._client, "is_closed", False) is True:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client


    def _build_cache_key(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        mode: str,
    ) -> str:
        return f"route:v1:{origin[0]:.5f},{origin[1]:.5f}:{destination[0]:.5f},{destination[1]:.5f}:{mode}"

    async def _get_cached_route(self, cache_key: str) -> RouteDetails | None:
        if not self._cache:
            return None
        try:
            cached_data = await self._cache.get(cache_key)
            if cached_data:
                parsed = json.loads(cached_data) if isinstance(cached_data, str) else cached_data
                return RouteDetails(
                    origin_coordinates=tuple(parsed["origin_coordinates"]),  # type: ignore[arg-type]
                    destination_coordinates=tuple(parsed["destination_coordinates"]),  # type: ignore[arg-type]
                    distance_meters=int(parsed["distance_meters"]),
                    duration_seconds=int(parsed["duration_seconds"]),
                    travel_mode=parsed.get("travel_mode", TravelMode.DRIVE.value),
                    is_fallback=bool(parsed.get("is_fallback", False)),
                    provider_metadata=parsed.get("provider_metadata", {}),
                )
        except Exception as exc:
            logger.debug("Failed to read routing cache key %s: %s", cache_key, exc)
        return None

    async def _set_cached_route(self, cache_key: str, route: RouteDetails) -> None:
        if not self._cache:
            return
        try:
            payload = {
                "origin_coordinates": route.origin_coordinates,
                "destination_coordinates": route.destination_coordinates,
                "distance_meters": route.distance_meters,
                "duration_seconds": route.duration_seconds,
                "travel_mode": route.travel_mode,
                "is_fallback": route.is_fallback,
                "provider_metadata": route.provider_metadata,
            }
            await self._cache.set(cache_key, json.dumps(payload), ttl=self._cache_ttl)
        except Exception as exc:
            logger.debug("Failed to write routing cache key %s: %s", cache_key, exc)

    async def _execute_with_retry(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute GET request against Directions API with exponential backoff."""
        params_with_key = {**params, "key": self._api_key}
        client = await self._get_client()

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = await client.get(_DIRECTIONS_BASE_URL, params=params_with_key)
                if response.status_code == 429:
                    raise ExternalServiceError(
                        "google_routing", "Google Directions rate limit exceeded (HTTP 429)."
                    )
                if response.status_code >= 500:
                    response.raise_for_status()

                data = response.json()
                status = data.get("status")

                if status in ("OK", "ZERO_RESULTS", "NOT_FOUND"):
                    return data
                if status == "OVER_QUERY_LIMIT":
                    raise ExternalServiceError(
                        "google_routing", "Google Directions quota or query limit exceeded."
                    )
                if status == "REQUEST_DENIED":
                    error_msg = data.get("error_message", "Request denied by Google Directions API.")
                    logger.error("Google Directions authentication denied: %s", error_msg)
                    raise ExternalServiceError(
                        "google_routing", "Google Directions API authentication or permissions failed."
                    )
                if status == "INVALID_REQUEST":
                    logger.warning("Invalid request to Google Directions API: %s", data.get("error_message"))
                    return data

                raise ExternalServiceError(
                    "google_routing", f"Google Directions returned unexpected status: {status}"
                )

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.warning(
                        "Google Directions request failed (attempt %d/%d): %s. Retrying in %.2fs...",
                        attempt,
                        self._max_retries,
                        exc,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                else:
                    logger.error("Google Directions request failed after %d attempts: %s", self._max_retries, exc)

        raise ExternalServiceError(
            "google_routing",
            f"Google Directions API unavailable after {self._max_retries} attempts: {last_exc}",
        )

    async def get_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        travel_mode: str = TravelMode.DRIVE.value,
    ) -> RouteDetails | None:
        """Calculate route between two verified coordinates via Google Directions API."""
        cache_key = self._build_cache_key(origin, destination, travel_mode)
        cached = await self._get_cached_route(cache_key)
        if cached is not None:
            return cached

        google_mode = _GOOGLE_MODE_MAP.get(travel_mode, "driving")
        params = {
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            "mode": google_mode,
        }

        try:
            data = await self._execute_with_retry(params)
        except ExternalServiceError:
            raise
        except Exception as exc:
            logger.error("Unexpected error querying Google Directions API: %s", exc)
            return None

        status = data.get("status")
        if status != "OK" or not data.get("routes"):
            return None

        primary_route = data["routes"][0]
        legs = primary_route.get("legs", [])
        if not legs:
            return None

        # Aggregate legs if multiple legs exist
        total_distance = sum(leg.get("distance", {}).get("value", 0) for leg in legs)
        total_duration = sum(leg.get("duration", {}).get("value", 0) for leg in legs)
        summary = primary_route.get("summary", "")
        overview_polyline = primary_route.get("overview_polyline", {}).get("points", "")

        route = RouteDetails(
            origin_coordinates=origin,
            destination_coordinates=destination,
            distance_meters=total_distance,
            duration_seconds=total_duration,
            travel_mode=travel_mode,
            is_fallback=False,
            provider_metadata={
                "summary": summary,
                "overview_polyline": overview_polyline,
                "status": status,
                "provider": "google_directions",
            },
        )

        await self._set_cached_route(cache_key, route)
        return route
