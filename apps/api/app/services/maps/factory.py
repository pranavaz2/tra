"""Maps provider factory."""

from __future__ import annotations

from app.config import get_settings
from app.services.maps.base import MapsProvider
from app.services.maps.mock import MockMapsProvider


def get_maps_provider() -> MapsProvider:
    """Return the configured maps provider implementation."""
    settings = get_settings()
    if settings.maps_provider == "mock":
        return MockMapsProvider()
    return MockMapsProvider()
