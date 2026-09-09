"""Provider-neutral routing and travel-time service interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class TravelMode(str, Enum):
    """Supported transportation modes for route calculation."""

    DRIVE = "drive"
    WALK = "walk"
    BICYCLE = "bicycle"
    TRANSIT = "transit"


@dataclass(frozen=True)
class RouteDetails:
    """Structured route calculation result between two geographic coordinates."""

    origin_coordinates: tuple[float, float]
    destination_coordinates: tuple[float, float]
    distance_meters: int
    duration_seconds: int
    travel_mode: str = TravelMode.DRIVE.value
    is_fallback: bool = False
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def distance_km(self) -> float:
        """Distance in kilometers."""
        return round(self.distance_meters / 1000.0, 2)

    @property
    def duration_minutes(self) -> int:
        """Estimated duration in integer minutes (rounded)."""
        return max(1, round(self.duration_seconds / 60.0)) if self.duration_seconds > 0 else 0


@runtime_checkable
class RoutingProvider(Protocol):
    """
    Abstract Routing provider contract.

    Supports route distance and travel duration calculations between verified locations.
    """

    async def get_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        travel_mode: str = TravelMode.DRIVE.value,
    ) -> RouteDetails | None:
        """
        Calculate route distance and estimated travel duration between origin and destination.

        Returns None if no route could be found or endpoints are invalid.
        """
        ...
