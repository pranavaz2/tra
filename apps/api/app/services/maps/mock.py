"""Mock maps and places provider for local development and tests."""

from __future__ import annotations

import math
from app.services.maps.base import (
    GeocodedPlace,
    MapsProvider,
    PlaceDetails,
    PlacePrediction,
    PlacesProvider,
)
from app.services.maps.route import RouteDetails, RoutingProvider, TravelMode
from app.shared.domain.errors import ExternalServiceError



class MockPlacesProvider(PlacesProvider, MapsProvider):
    """
    Deterministic places & maps provider that never calls external services.

    Pre-seeded with known canonical places and supports custom seeding for tests.
    """

    def __init__(self, initial_places: list[PlaceDetails] | None = None) -> None:
        self._places: dict[str, PlaceDetails] = {}
        # Pre-seed default global landmarks
        default_places = [
            PlaceDetails(
                provider_place_id="mock_place_colosseum",
                name="Colosseum",
                formatted_address="Piazza del Colosseo, 1, 00184 Roma RM, Italy",
                latitude=41.890210,
                longitude=12.492231,
                country_code="IT",
                region="Lazio",
                locality="Rome",
                types=["tourist_attraction", "historical_landmark"],
                rating=4.7,
                user_ratings_total=350000,
                opening_hours=["Monday: 8:30 AM - 7:00 PM", "Tuesday: 8:30 AM - 7:00 PM"],
                is_open_now=True,
            ),
            PlaceDetails(
                provider_place_id="mock_place_eiffel_tower",
                name="Eiffel Tower",
                formatted_address="Champ de Mars, 5 Av. Anatole France, 75007 Paris, France",
                latitude=48.858370,
                longitude=2.294481,
                country_code="FR",
                region="Île-de-France",
                locality="Paris",
                types=["tourist_attraction", "point_of_interest"],
                rating=4.6,
                user_ratings_total=400000,
                opening_hours=["Monday: 9:00 AM - 11:45 PM"],
                is_open_now=True,
            ),
            PlaceDetails(
                provider_place_id="mock_place_tokyo_tower",
                name="Tokyo Tower",
                formatted_address="4 Chome-2-8 Shibakoen, Minato City, Tokyo 105-0011, Japan",
                latitude=35.658580,
                longitude=139.745433,
                country_code="JP",
                region="Kanto",
                locality="Tokyo",
                types=["tourist_attraction", "point_of_interest"],
                rating=4.5,
                user_ratings_total=80000,
                opening_hours=["Monday: 9:00 AM - 10:30 PM"],
                is_open_now=True,
            ),
            PlaceDetails(
                provider_place_id="mock_place_trattoria_enzo",
                name="Trattoria Da Enzo al 29",
                formatted_address="Via dei Vascellari, 29, 00153 Roma RM, Italy",
                latitude=41.887550,
                longitude=12.477280,
                country_code="IT",
                region="Lazio",
                locality="Rome",
                types=["restaurant", "food", "point_of_interest"],
                rating=4.4,
                user_ratings_total=3200,
                opening_hours=["Monday: 12:15 - 3:00 PM, 7:30 - 11:00 PM"],
                is_open_now=True,
            ),
            PlaceDetails(
                provider_place_id="mock_place_vatican_museums",
                name="Vatican Museums",
                formatted_address="00120 Vatican City",
                latitude=41.906389,
                longitude=12.454444,
                country_code="VA",
                region="Vatican",
                locality="Vatican City",
                types=["museum", "tourist_attraction"],
                rating=4.6,
                user_ratings_total=180000,
                opening_hours=["Monday: 8:00 AM - 7:00 PM"],
                is_open_now=True,
            ),
            PlaceDetails(
                provider_place_id="mock_place_caffe_greco",
                name="Antico Caffè Greco",
                formatted_address="Via dei Condotti, 86, 00187 Roma RM, Italy",
                latitude=41.905600,
                longitude=12.482300,
                country_code="IT",
                region="Lazio",
                locality="Rome",
                types=["cafe", "coffee", "food", "restaurant"],
                rating=4.3,
                user_ratings_total=5400,
                opening_hours=["Monday: 9:00 AM - 9:00 PM"],
                is_open_now=True,
            ),
            PlaceDetails(
                provider_place_id="mock_place_kichi_omurice",
                name="Kichi Kichi Omurice",
                formatted_address="185-1 Zaimokucho, Nakagyo Ward, Kyoto, 604-8017, Japan",
                latitude=35.006800,
                longitude=135.771200,
                country_code="JP",
                region="Kansai",
                locality="Kyoto",
                types=["restaurant", "food", "vegetarian"],
                rating=4.7,
                user_ratings_total=4200,
                opening_hours=["Monday: 11:30 AM - 2:00 PM, 5:00 - 9:00 PM"],
                is_open_now=True,
            ),
        ]
        for p in default_places:
            self._places[p.provider_place_id] = p


        if initial_places:
            for p in initial_places:
                self._places[p.provider_place_id] = p

    def add_place(self, place: PlaceDetails) -> None:
        """Register a mock place for testing."""
        self._places[place.provider_place_id] = place

    async def text_search(
        self,
        query: str,
        *,
        location: tuple[float, float] | None = None,
        radius_meters: int | None = None,
    ) -> list[PlaceDetails]:
        """Search registered mock places by substring match on name or address."""
        q = query.lower().strip()
        if not q:
            return []

        results: list[PlaceDetails] = []
        for p in self._places.values():
            if (
                q in p.name.lower()
                or p.name.lower() in q
                or q in p.formatted_address.lower()
                or any(t in q for t in p.types)
            ):
                results.append(p)
        return results

    async def autocomplete(
        self,
        input_text: str,
        *,
        location: tuple[float, float] | None = None,
        radius_meters: int | None = None,
    ) -> list[PlacePrediction]:
        """Return autocomplete predictions from registered mock places."""
        matches = await self.text_search(input_text, location=location, radius_meters=radius_meters)
        return [
            PlacePrediction(
                provider_place_id=p.provider_place_id,
                description=f"{p.name}, {p.formatted_address}",
                primary_text=p.name,
                secondary_text=p.locality or p.region,
                types=p.types,
            )
            for p in matches
        ]

    async def get_place_details(self, place_id: str) -> PlaceDetails | None:
        """Fetch place details by place ID."""
        return self._places.get(place_id)

    async def nearby_search(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_meters: int,
        place_type: str | None = None,
    ) -> list[PlaceDetails]:
        """Return registered mock places within approximate coordinate distance."""
        # Simple bounding-box approximation: ~111km per degree
        max_deg = radius_meters / 111000.0
        results: list[PlaceDetails] = []
        for p in self._places.values():
            if abs(p.latitude - latitude) <= max_deg and abs(p.longitude - longitude) <= max_deg:
                if place_type is None or place_type in p.types:
                    results.append(p)
        return results

    async def geocode(self, query: str) -> list[GeocodedPlace]:
        """Geocode query string using registered mock places."""
        matches = await self.text_search(query)
        if matches:
            return [
                GeocodedPlace(
                    name=p.name,
                    country_code=p.country_code or "US",
                    latitude=p.latitude,
                    longitude=p.longitude,
                    region=p.region,
                    locality=p.locality,
                    provider_place_id=p.provider_place_id,
                )
                for p in matches
            ]
        return []


# Backward-compatibility alias
MockMapsProvider = MockPlacesProvider


def _calc_haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Helper great-circle distance in kilometers."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_km * c


class MockRoutingProvider(RoutingProvider):
    """
    Deterministic mock routing provider for testing and offline development.

    Supports pre-seeded exact routes, realistic simulated travel times based on mode,
    and simulated error/timeout testing.
    """

    def __init__(
        self,
        custom_routes: dict[tuple[tuple[float, float], tuple[float, float]], RouteDetails] | None = None,
        *,
        simulate_failure: bool = False,
        simulate_rate_limit: bool = False,
    ) -> None:
        self._custom_routes: dict[tuple[tuple[float, float], tuple[float, float]], RouteDetails] = (
            custom_routes or {}
        )
        self.simulate_failure = simulate_failure
        self.simulate_rate_limit = simulate_rate_limit

    def register_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        route: RouteDetails,
    ) -> None:
        """Register a specific deterministic route."""
        self._custom_routes[(origin, destination)] = route

    async def get_route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        travel_mode: str = TravelMode.DRIVE.value,
    ) -> RouteDetails | None:
        """Calculate deterministic route or return registered mock route."""
        if self.simulate_rate_limit:
            raise ExternalServiceError("mock_routing", "Mock rate limit exceeded (HTTP 429).")

        if self.simulate_failure:
            raise ExternalServiceError("mock_routing", "Simulated routing provider failure.")

        # Check registered custom routes first
        if (origin, destination) in self._custom_routes:
            return self._custom_routes[(origin, destination)]

        # Check reverse if same mode
        if (destination, origin) in self._custom_routes:
            rev = self._custom_routes[(destination, origin)]
            return RouteDetails(
                origin_coordinates=origin,
                destination_coordinates=destination,
                distance_meters=rev.distance_meters,
                duration_seconds=rev.duration_seconds,
                travel_mode=rev.travel_mode,
                is_fallback=rev.is_fallback,
                provider_metadata={"mock": True, "reversed": True},
            )

        dist_km = _calc_haversine_km(origin[0], origin[1], destination[0], destination[1])

        # If origin and destination are identical
        if dist_km < 0.001:
            return RouteDetails(
                origin_coordinates=origin,
                destination_coordinates=destination,
                distance_meters=0,
                duration_seconds=0,
                travel_mode=travel_mode,
                is_fallback=False,
                provider_metadata={"mock": True, "same_location": True},
            )

        # Realistic urban routing estimation based on mode
        # Driving: ~35 km/h in urban areas + route winding factor 1.25
        # Walking: ~4.5 km/h
        # Bicycle: ~15 km/h
        # Transit: ~22 km/h + 300s overhead
        winding_factor = 1.25
        actual_distance_km = dist_km * winding_factor
        distance_meters = int(actual_distance_km * 1000)

        if travel_mode == TravelMode.WALK.value:
            speed_kmh = 4.5
            overhead_sec = 0
        elif travel_mode == TravelMode.BICYCLE.value:
            speed_kmh = 15.0
            overhead_sec = 60
        elif travel_mode == TravelMode.TRANSIT.value:
            speed_kmh = 22.0
            overhead_sec = 300
        else:  # DRIVE
            speed_kmh = 35.0
            overhead_sec = 120  # traffic & parking buffer

        duration_seconds = int((actual_distance_km / speed_kmh) * 3600) + overhead_sec

        return RouteDetails(
            origin_coordinates=origin,
            destination_coordinates=destination,
            distance_meters=distance_meters,
            duration_seconds=max(60, duration_seconds),
            travel_mode=travel_mode,
            is_fallback=False,
            provider_metadata={"mock": True, "simulated_speed_kmh": speed_kmh},
        )

