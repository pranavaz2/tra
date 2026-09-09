"""Maps and Places provider factory."""

from __future__ import annotations

from app.config import get_settings
from app.services.maps.base import MapsProvider, PlacesProvider
from app.services.maps.google import GooglePlacesProvider
from app.services.maps.google_routing import GoogleRoutingProvider
from app.services.maps.mock import MockPlacesProvider, MockRoutingProvider
from app.services.maps.nominatim import NominatimPlacesProvider
from app.services.maps.route import RoutingProvider
import logging

logger = logging.getLogger(__name__)


def get_places_provider() -> PlacesProvider:
    """Return the configured PlacesProvider implementation."""
    settings = get_settings()
    provider_type = getattr(settings, "places_provider", None) or settings.maps_provider

    if provider_type == "osm":
        logger.info("PlacesProvider: NominatimPlacesProvider active (OpenStreetMap — free, no key required)")
        return NominatimPlacesProvider()

    if provider_type == "google":
        key = (
            getattr(settings, "google_places_api_key", None) or settings.google_maps_server_api_key
        )
        if key and key.get_secret_value():
            cache = None
            try:
                from app.redis import get_cache_backend

                cache = get_cache_backend()
            except Exception as exc:
                logger.debug("Places cache backend unavailable: %s", exc)
            logger.info("PlacesProvider: GooglePlacesProvider active")
            return GooglePlacesProvider(
                api_key=key.get_secret_value(),
                cache_client=cache,
            )
        else:
            # Google selected but no key — fall back to OSM (free) instead of mock
            logger.warning(
                "PlacesProvider: PLACES_PROVIDER=google but no API key found. "
                "Falling back to NominatimPlacesProvider (free OSM). "
                "Set GOOGLE_MAPS_SERVER_API_KEY to use Google Places."
            )
            return NominatimPlacesProvider()

    logger.info("PlacesProvider: MockPlacesProvider active")
    return MockPlacesProvider()


def get_maps_provider() -> MapsProvider:
    """Return the configured MapsProvider (also satisfies PlacesProvider)."""
    return get_places_provider()


def get_routing_provider() -> RoutingProvider:
    """Return the configured RoutingProvider implementation."""
    settings = get_settings()
    provider_type = getattr(settings, "routing_provider", None) or settings.maps_provider

    if provider_type == "google":
        key = (
            getattr(settings, "google_maps_server_api_key", None)
            or getattr(settings, "google_places_api_key", None)
        )
        if key:
            cache = None
            try:
                from app.redis import get_cache_backend

                cache = get_cache_backend()
            except Exception as exc:
                logger.debug("Routing cache backend unavailable: %s", exc)
            return GoogleRoutingProvider(
                api_key=key.get_secret_value(),
                cache_client=cache,
            )

    return MockRoutingProvider()

