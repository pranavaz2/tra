"""Unit tests for RoutingProvider abstraction, GoogleRoutingProvider, MockRoutingProvider, and RouteDetails."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.maps.base import PlacesProvider
from app.services.maps.factory import get_routing_provider
from app.services.maps.google_routing import GoogleRoutingProvider
from app.services.maps.mock import MockRoutingProvider
from app.services.maps.route import RouteDetails, RoutingProvider, TravelMode
from app.shared.domain.errors import ExternalServiceError


class TestRouteDetails:
    def test_route_details_properties(self) -> None:
        route = RouteDetails(
            origin_coordinates=(41.8902, 12.4922),
            destination_coordinates=(41.8875, 12.4772),
            distance_meters=2450,
            duration_seconds=540,
            travel_mode=TravelMode.DRIVE.value,
            is_fallback=False,
            provider_metadata={"summary": "Via Via dei Fori Imperiali"},
        )
        assert route.distance_km == 2.45
        assert route.duration_minutes == 9
        assert not route.is_fallback
        assert route.travel_mode == "drive"

    def test_zero_duration_minutes(self) -> None:
        route = RouteDetails(
            origin_coordinates=(0.0, 0.0),
            destination_coordinates=(0.0, 0.0),
            distance_meters=0,
            duration_seconds=0,
        )
        assert route.duration_minutes == 0
        assert route.distance_km == 0.0


class TestMockRoutingProvider:
    @pytest.mark.asyncio
    async def test_deterministic_route_calculation(self) -> None:
        provider = MockRoutingProvider()
        # Colosseum to Trattoria Da Enzo (Rome ~1.5 km straight line)
        origin = (41.8902, 12.4922)
        dest = (41.8875, 12.4772)
        route = await provider.get_route(origin, dest, travel_mode=TravelMode.DRIVE.value)

        assert route is not None
        assert route.origin_coordinates == origin
        assert route.destination_coordinates == dest
        assert route.distance_meters > 0
        assert route.duration_seconds > 0
        assert route.distance_km > 1.0
        assert not route.is_fallback
        assert route.travel_mode == "drive"

    @pytest.mark.asyncio
    async def test_registered_custom_route(self) -> None:
        provider = MockRoutingProvider()
        origin = (48.8584, 2.2945)
        dest = (48.8606, 2.3376)
        custom = RouteDetails(
            origin_coordinates=origin,
            destination_coordinates=dest,
            distance_meters=4100,
            duration_seconds=900,
            travel_mode=TravelMode.DRIVE.value,
        )
        provider.register_route(origin, dest, custom)

        route = await provider.get_route(origin, dest)
        assert route is not None
        assert route.distance_meters == 4100
        assert route.duration_seconds == 900
        assert route.duration_minutes == 15

    @pytest.mark.asyncio
    async def test_travel_modes_produce_different_durations(self) -> None:
        provider = MockRoutingProvider()
        origin = (41.8902, 12.4922)
        dest = (41.9064, 12.4544)  # Colosseum to Vatican (~3.7 km)

        walk_route = await provider.get_route(origin, dest, travel_mode=TravelMode.WALK.value)
        drive_route = await provider.get_route(origin, dest, travel_mode=TravelMode.DRIVE.value)

        assert walk_route is not None
        assert drive_route is not None
        # Walking should take significantly longer than driving
        assert walk_route.duration_seconds > drive_route.duration_seconds

    @pytest.mark.asyncio
    async def test_same_location_zero_route(self) -> None:
        provider = MockRoutingProvider()
        coords = (41.8902, 12.4922)
        route = await provider.get_route(coords, coords)
        assert route is not None
        assert route.distance_meters == 0
        assert route.duration_seconds == 0
        assert route.duration_minutes == 0

    @pytest.mark.asyncio
    async def test_simulated_failure(self) -> None:
        provider = MockRoutingProvider(simulate_failure=True)
        with pytest.raises(ExternalServiceError) as exc_info:
            await provider.get_route((41.0, 12.0), (41.5, 12.5))
        assert "Simulated routing provider failure" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_simulated_rate_limit(self) -> None:
        provider = MockRoutingProvider(simulate_rate_limit=True)
        with pytest.raises(ExternalServiceError) as exc_info:
            await provider.get_route((41.0, 12.0), (41.5, 12.5))
        assert "Mock rate limit exceeded" in str(exc_info.value)


class TestGoogleRoutingProvider:
    @pytest.mark.asyncio
    async def test_successful_directions_mapping(self) -> None:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "OK",
            "routes": [
                {
                    "summary": "SS1",
                    "overview_polyline": {"points": "a~l~Fjk~uOw..."},
                    "legs": [
                        {
                            "distance": {"value": 12450, "text": "12.5 km"},
                            "duration": {"value": 2040, "text": "34 mins"},
                        }
                    ],
                }
            ],
        }
        mock_http.get.return_value = mock_response

        provider = GoogleRoutingProvider(
            api_key="test_api_key",
            http_client=mock_http,
        )

        origin = (41.8902, 12.4922)
        dest = (41.8875, 12.4772)
        route = await provider.get_route(origin, dest, travel_mode=TravelMode.DRIVE.value)

        assert route is not None
        assert route.distance_meters == 12450
        assert route.duration_seconds == 2040
        assert route.distance_km == 12.45
        assert route.duration_minutes == 34
        assert not route.is_fallback
        assert route.provider_metadata["summary"] == "SS1"

    @pytest.mark.asyncio
    async def test_caching_behavior(self) -> None:
        mock_cache = AsyncMock()
        cached_payload = json.dumps({
            "origin_coordinates": [41.89, 12.49],
            "destination_coordinates": [41.88, 12.47],
            "distance_meters": 3200,
            "duration_seconds": 600,
            "travel_mode": "drive",
            "is_fallback": False,
            "provider_metadata": {"cached": True},
        })
        mock_cache.get.return_value = cached_payload

        mock_http = AsyncMock()

        provider = GoogleRoutingProvider(
            api_key="test_api_key",
            cache_client=mock_cache,
            http_client=mock_http,
        )

        route = await provider.get_route((41.89, 12.49), (41.88, 12.47))
        assert route is not None
        assert route.distance_meters == 3200
        assert route.duration_seconds == 600
        # HTTP client should not have been called due to cache hit
        assert mock_http.get.call_count == 0

    @pytest.mark.asyncio
    async def test_rate_limit_429_raises_external_error(self) -> None:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_http.get.return_value = mock_response

        provider = GoogleRoutingProvider(
            api_key="test_api_key",
            http_client=mock_http,
            max_retries=1,
        )

        with pytest.raises(ExternalServiceError) as exc_info:
            await provider.get_route((41.89, 12.49), (41.88, 12.47))
        assert "rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_zero_results_returns_none(self) -> None:
        mock_http = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ZERO_RESULTS",
            "routes": [],
        }
        mock_http.get.return_value = mock_response

        provider = GoogleRoutingProvider(
            api_key="test_api_key",
            http_client=mock_http,
        )

        route = await provider.get_route((0.0, 0.0), (10.0, 10.0))
        assert route is None

    @pytest.mark.asyncio
    async def test_empty_api_key_raises_error(self) -> None:
        with pytest.raises(ValueError):
            GoogleRoutingProvider(api_key="")


class TestFactory:
    def test_get_routing_provider_default_mock(self) -> None:
        provider = get_routing_provider()
        assert isinstance(provider, MockRoutingProvider)
