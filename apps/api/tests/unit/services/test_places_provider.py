"""Unit tests for Places and Maps providers (Mock and Google)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import get_settings
from app.services.maps.factory import get_maps_provider, get_places_provider
from app.services.maps.google import GooglePlacesProvider
from app.services.maps.mock import MockPlacesProvider
from app.shared.domain.errors import ExternalServiceError


@pytest.mark.asyncio
async def test_mock_places_provider_search_and_details() -> None:
    provider = MockPlacesProvider()

    # Search known landmark
    results = await provider.text_search("Colosseum")
    assert len(results) >= 1
    assert results[0].name == "Colosseum"
    assert results[0].latitude == 41.890210
    assert results[0].country_code == "IT"
    assert results[0].is_open_now is True

    # Get details
    details = await provider.get_place_details(results[0].provider_place_id)
    assert details is not None
    assert details.name == "Colosseum"

    # Search unknown returns empty
    unknown = await provider.text_search("Nonexistent Fictional Atlantis 9999")
    assert len(unknown) == 0


@pytest.mark.asyncio
async def test_mock_places_provider_autocomplete_and_nearby() -> None:
    provider = MockPlacesProvider()

    # Autocomplete
    predictions = await provider.autocomplete("Eiffel")
    assert len(predictions) >= 1
    assert "Eiffel Tower" in predictions[0].description

    # Nearby search around Rome (41.89, 12.49) within 5km
    nearby = await provider.nearby_search(latitude=41.89, longitude=12.49, radius_meters=5000)
    names = [p.name for p in nearby]
    assert "Colosseum" in names

    # Geocode
    geo = await provider.geocode("Tokyo Tower")
    assert len(geo) >= 1
    assert geo[0].country_code == "JP"


@pytest.mark.asyncio
async def test_google_places_provider_text_search_success() -> None:
    fake_response_data = {
        "status": "OK",
        "results": [
            {
                "place_id": "ChIJ_test_123",
                "name": "Senso-ji",
                "formatted_address": "2 Chome-3-1 Asakusa, Taito City, Tokyo 111-0032, Japan",
                "geometry": {"location": {"lat": 35.7147, "lng": 139.7966}},
                "types": ["tourist_attraction", "place_of_worship"],
                "rating": 4.6,
                "user_ratings_total": 45000,
                "opening_hours": {
                    "open_now": True,
                    "weekday_text": ["Monday: 6:00 AM - 5:00 PM"],
                },
                "address_components": [
                    {"long_name": "Japan", "short_name": "JP", "types": ["country"]},
                    {"long_name": "Tokyo", "short_name": "Tokyo", "types": ["locality"]},
                ],
            }
        ],
    }

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response_data
    mock_client.get.return_value = mock_resp

    provider = GooglePlacesProvider("fake-api-key", http_client=mock_client)
    places = await provider.text_search("Senso-ji, Tokyo")

    assert len(places) == 1
    place = places[0]
    assert place.provider_place_id == "ChIJ_test_123"
    assert place.name == "Senso-ji"
    assert place.latitude == 35.7147
    assert place.longitude == 139.7966
    assert place.rating == 4.6
    assert place.country_code == "JP"
    assert place.is_open_now is True


@pytest.mark.asyncio
async def test_google_places_provider_quota_error() -> None:
    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "OVER_QUERY_LIMIT",
        "error_message": "Quota exceeded",
    }
    mock_client.get.return_value = mock_resp

    provider = GooglePlacesProvider("fake-api-key", http_client=mock_client)
    with pytest.raises(ExternalServiceError) as exc_info:
        await provider.text_search("Rome")
    assert "quota or query limit exceeded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_google_places_provider_timeout_and_retry_failure() -> None:
    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.get.side_effect = httpx.TimeoutException("Connection timed out")

    provider = GooglePlacesProvider("fake-api-key", max_retries=2, http_client=mock_client)
    with pytest.raises(ExternalServiceError) as exc_info:
        await provider.get_place_details("ChIJ_dummy")
    assert "unavailable" in str(exc_info.value)


def test_places_provider_factory_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.maps.nominatim import NominatimPlacesProvider

    get_settings.cache_clear()

    # Mock when PLACES_PROVIDER=mock
    monkeypatch.setenv("PLACES_PROVIDER", "mock")
    get_settings.cache_clear()
    provider = get_places_provider()
    assert isinstance(provider, MockPlacesProvider)
    assert isinstance(get_maps_provider(), MockPlacesProvider)

    # OSM (free, no key) when PLACES_PROVIDER=osm
    monkeypatch.setenv("PLACES_PROVIDER", "osm")
    get_settings.cache_clear()
    osm_provider = get_places_provider()
    assert isinstance(osm_provider, NominatimPlacesProvider)

    # Google when PLACES_PROVIDER=google and key present
    monkeypatch.setenv("PLACES_PROVIDER", "google")
    monkeypatch.setenv("GOOGLE_MAPS_SERVER_API_KEY", "real-key-12345")
    get_settings.cache_clear()
    google_provider = get_places_provider()
    assert isinstance(google_provider, GooglePlacesProvider)

    get_settings.cache_clear()
