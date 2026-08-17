"""Unit tests for RecommendationService using in-memory doubles and stubs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.locations.repository import LocationRepository
from app.modules.travel.recommendations.application.commands import UpdatePreferencesCommand
from app.modules.travel.recommendations.application.queries import (
    GetNearbyRecommendationsQuery,
    GetRecommendationsQuery,
    GetSimilarTripsQuery,
    GetTrendingDestinationsQuery,
)
from app.modules.travel.recommendations.application.recommendation_service import (
    RecommendationService,
)
from app.modules.travel.recommendations.domain.entities.recommendation import (
    ActivityRecommendation,
    DestinationRecommendation,
    RestaurantRecommendation,
)
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences
from app.modules.travel.recommendations.domain.enums.budget_tier import BudgetTier
from app.modules.travel.recommendations.domain.enums.travel_pace import TravelPace
from app.modules.travel.recommendations.domain.enums.travel_style import TravelStyle
from app.modules.travel.recommendations.domain.repositories.interfaces import (
    IUserPreferencesRepository,
)
from app.modules.travel.recommendations.domain.services.interfaces import (
    PopularityProvider,
    RecommendationEngine,
    SimilarityEngine,
)
from app.modules.travel.recommendations.domain.value_objects.dietary_tag import DietaryTag
from app.modules.travel.recommendations.domain.value_objects.interest_tag import InterestTag
from app.modules.travel.recommendations.domain.value_objects.preferences_id import PreferencesId
from app.modules.travel.recommendations.domain.value_objects.recommendation_reason import (
    RecommendationReason,
)
from app.modules.travel.recommendations.domain.value_objects.recommendation_score import (
    RecommendationScore,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.shared.domain.errors import ValidationError
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider

# ─────────────────────────────────────────────────────────────────────────────
# Test Constants & Mock Entities
# ─────────────────────────────────────────────────────────────────────────────

FIXED_USER_UUID = UUID("11111111-1111-1111-1111-111111111111")
FIXED_TRIP_UUID = UUID("22222222-2222-2222-2222-222222222222")
FIXED_PREF_UUID = UUID("33333333-3333-3333-3333-333333333333")


# ─────────────────────────────────────────────────────────────────────────────
# Test Doubles
# ─────────────────────────────────────────────────────────────────────────────


class InMemoryUserPreferencesRepository(IUserPreferencesRepository):
    """In-memory UserPreferences repository double."""

    def __init__(self) -> None:
        self.store: dict[UUID, UserPreferences] = {}

    async def find_by_user_id(self, user_id: UserId) -> UserPreferences | None:
        return self.store.get(user_id.value)

    async def save(self, preferences: UserPreferences) -> None:
        if preferences.user_id.value in self.store:
            new_version = self.store[preferences.user_id.value].version + 1
            object.__setattr__(preferences, "version", new_version)
        self.store[preferences.user_id.value] = preferences


class InMemoryTripRepository(ITripRepository):
    """In-memory TripRepository double."""

    def __init__(self) -> None:
        self.trips: dict[UUID, Trip] = {}

    async def save(self, trip: Trip) -> None:
        self.trips[trip.entity_id.value] = trip

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self.trips.get(trip_id.value)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        status_filter: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[Trip], str | None]:
        return [], None

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        return []

    async def exists(self, trip_id: TripId) -> bool:
        return trip_id.value in self.trips

    async def exists_with_title(self, owner_id: UserId, title: TripTitle) -> bool:
        return False

    async def hard_delete(self, trip_id: TripId) -> None:
        self.trips.pop(trip_id.value, None)


class MockLocationRepository(LocationRepository):
    """Mock LocationRepository returning fixed items for nearby queries."""

    def __init__(self) -> None:
        # Avoid calling super.__init__ to bypass session setup
        pass

    async def find_nearby(
        self,
        *,
        latitude: Any,
        longitude: Any,
        radius_meters: int,
        limit: int = 20,
    ) -> list[Any]:
        # Return dummy locations
        class MockLocation:
            id = UUID("77777777-7777-7777-7777-777777777777")
            name = "Eiffel Tower"
            locality = "Paris"
            country_code = "FR"
            description = "Iconic iron tower."

        return [MockLocation()]


class StubRecommendationEngine:
    """Stub engine returning structured recommendations."""

    async def recommend_destinations(
        self, preferences: UserPreferences, limit: int = 10
    ) -> list[DestinationRecommendation]:
        return [
            DestinationRecommendation(
                entity_id=UUID("88888888-8888-8888-8888-888888888888"),
                title="Kyoto, Japan",
                description="Historic temples and gardens.",
                score=RecommendationScore(value=95),
                reason=RecommendationReason(value="Matches culture style."),
                location_id=UUID("88888888-8888-8888-8888-888888888888"),
                country_code="JP",
            )
        ][:limit]

    async def recommend_activities(
        self, preferences: UserPreferences, trip_id: UUID, limit: int = 10
    ) -> list[ActivityRecommendation]:
        return [
            ActivityRecommendation(
                entity_id=UUID("44444444-4444-4444-4444-444444444444"),
                title="Historic Walking Tour",
                score=RecommendationScore(value=92),
                reason=RecommendationReason(value="Aligned with pace."),
                activity_type="Sightseeing",
                trip_id=trip_id,
            )
        ][:limit]

    async def recommend_restaurants(
        self, preferences: UserPreferences, trip_id: UUID, limit: int = 10
    ) -> list[RestaurantRecommendation]:
        return [
            RestaurantRecommendation(
                entity_id=UUID("55555555-5555-5555-5555-555555555555"),
                title="The Gourmet Vegan",
                score=RecommendationScore(value=89),
                reason=RecommendationReason(value="Vegan cuisine match."),
                cuisine_type="Vegan",
                trip_id=trip_id,
            )
        ][:limit]


class StubSimilarityEngine(SimilarityEngine):
    """Stub similarity engine."""

    async def find_similar_trips(self, trip_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        return [
            {
                "trip_id": UUID("99999999-9999-9999-9999-999999999999"),
                "title": "Historical Kyoto Explorer",
                "score": 90,
                "reason": "Shares similar culture tags.",
            }
        ][:limit]


class StubPopularityProvider(PopularityProvider):
    """Stub popularity provider."""

    async def get_popular_destinations(self, limit: int = 10) -> list[DestinationRecommendation]:
        return [
            DestinationRecommendation(
                entity_id=UUID("66666666-6666-6666-6666-666666666666"),
                title="Rome, Italy",
                score=RecommendationScore(value=98),
                reason=RecommendationReason(value="Globally trending."),
                location_id=UUID("66666666-6666-6666-6666-666666666666"),
                country_code="IT",
            )
        ][:limit]


class DummyUnitOfWork(UnitOfWork):
    """No-op unit of work double."""

    async def __aenter__(self) -> DummyUnitOfWork:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FixedUUIDProvider(UUIDProvider):
    """UUID provider returning a fixed value."""

    def __init__(self, value: UUID) -> None:
        self.value = value

    def generate(self) -> UUID:
        return self.value


class InMemoryEventPublisher(EventPublisher):
    """Event publisher capturing all fired events."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _make_service() -> tuple[
    RecommendationService,
    InMemoryUserPreferencesRepository,
    InMemoryTripRepository,
    InMemoryEventPublisher,
]:
    pref_repo = InMemoryUserPreferencesRepository()
    trip_repo = InMemoryTripRepository()
    loc_repo = MockLocationRepository()
    rec_engine = StubRecommendationEngine()
    sim_engine = StubSimilarityEngine()
    pop_provider = StubPopularityProvider()
    uow = DummyUnitOfWork()
    uuid_prov = FixedUUIDProvider(FIXED_PREF_UUID)
    pub = InMemoryEventPublisher()

    service = RecommendationService(
        preferences_repository=pref_repo,
        trip_repository=trip_repo,
        location_repository=loc_repo,
        recommendation_engine=rec_engine,
        similarity_engine=sim_engine,
        popularity_provider=pop_provider,
        uow=uow,
        uuid_provider=uuid_prov,
        event_publisher=pub,
    )
    return service, pref_repo, trip_repo, pub


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_preferences_creates_new() -> None:
    """update_preferences should create new preferences if none exist for a user."""
    service, pref_repo, _, pub = _make_service()

    cmd = UpdatePreferencesCommand(
        user_id=str(FIXED_USER_UUID),
        interests=["culture", "food"],
        dietary_preferences=["vegan"],
        travel_style="food",
        travel_pace="fast",
        budget_tier="luxury",
    )

    result = await service.update_preferences(cmd)
    assert isinstance(result, Success)
    dto = result.value
    assert dto.user_id == str(FIXED_USER_UUID)
    assert dto.interests == ["culture", "food"]
    assert dto.travel_style == "food"

    # Verify db save
    preferences = await pref_repo.find_by_user_id(UserId(value=FIXED_USER_UUID))
    assert preferences is not None
    assert preferences.entity_id == PreferencesId(value=FIXED_PREF_UUID)

    # Verify events published
    assert len(pub.events) == 1
    assert pub.events[0].user_id == str(FIXED_USER_UUID)


@pytest.mark.asyncio
async def test_update_preferences_updates_existing() -> None:
    """update_preferences should update preferences in-place if they exist."""
    service, pref_repo, _, pub = _make_service()

    # Pre-create preferences
    pid = PreferencesId(value=FIXED_PREF_UUID)
    uid = UserId(value=FIXED_USER_UUID)
    existing = UserPreferences.create(
        preferences_id=pid,
        user_id=uid,
        interests=[InterestTag("nature")],
        dietary_preferences=[],
        travel_style=TravelStyle.NATURE,
        travel_pace=TravelPace.SLOW,
        budget_tier=BudgetTier.BUDGET,
    )
    await pref_repo.save(existing)

    cmd = UpdatePreferencesCommand(
        user_id=str(FIXED_USER_UUID),
        interests=["culture"],
        dietary_preferences=["vegetarian"],
        travel_style="culture",
        travel_pace="medium",
        budget_tier="mid_range",
    )

    pub.events.clear()
    result = await service.update_preferences(cmd)
    assert isinstance(result, Success)
    dto = result.value
    assert dto.interests == ["culture"]

    # Verify version lock increments
    preferences = await pref_repo.find_by_user_id(uid)
    assert preferences.version == 2


@pytest.mark.asyncio
async def test_get_preferences_returns_error_if_missing() -> None:
    """get_preferences should fail with UserPreferencesNotFoundError if preferences do not exist."""
    service, _, _, _ = _make_service()
    result = await service.get_preferences(str(FIXED_USER_UUID))
    assert isinstance(result, Failure)
    assert result.error.code == "user_preferences_not_found"


@pytest.mark.asyncio
async def test_get_recommendations_success() -> None:
    """get_recommendations should return grouped recommendations successfully."""
    service, pref_repo, trip_repo, _ = _make_service()

    # Save preferences & trip
    uid = UserId(value=FIXED_USER_UUID)
    existing = UserPreferences.create(
        preferences_id=PreferencesId(value=FIXED_PREF_UUID),
        user_id=uid,
        interests=[InterestTag("culture")],
        dietary_preferences=[DietaryTag("vegan")],
        travel_style=TravelStyle.CULTURE,
        travel_pace=TravelPace.MEDIUM,
        budget_tier=BudgetTier.MID_RANGE,
    )
    await pref_repo.save(existing)

    trip = Trip(
        entity_id=TripId(value=FIXED_TRIP_UUID),
        owner_id=uid,
        title=TripTitle(value="My Trip"),
        status=TripStatus.DRAFT,
        privacy=TripPrivacy.PRIVATE,
        date_range=None,
    )
    await trip_repo.save(trip)

    query = GetRecommendationsQuery(
        user_id=str(FIXED_USER_UUID),
        trip_id=str(FIXED_TRIP_UUID),
        limit=5,
    )

    result = await service.get_recommendations(query)
    assert isinstance(result, Success)
    dto = result.value
    assert len(dto.destinations) == 1
    assert dto.destinations[0].title == "Kyoto, Japan"
    assert len(dto.activities) == 1
    assert len(dto.restaurants) == 1


@pytest.mark.asyncio
async def test_get_trending_destinations_success() -> None:
    """get_trending_destinations should fetch globally popular items successfully."""
    service, _, _, _ = _make_service()
    query = GetTrendingDestinationsQuery(limit=5)
    result = await service.get_trending_destinations(query)
    assert isinstance(result, Success)
    assert len(result.value) == 1
    assert result.value[0].title == "Rome, Italy"


@pytest.mark.asyncio
async def test_get_nearby_recommendations_success() -> None:
    """get_nearby_recommendations should query location repo and return recommendations."""
    service, pref_repo, _, _ = _make_service()

    # Save preferences
    uid = UserId(value=FIXED_USER_UUID)
    existing = UserPreferences.create(
        preferences_id=PreferencesId(value=FIXED_PREF_UUID),
        user_id=uid,
        interests=[InterestTag("culture")],
        dietary_preferences=[],
        travel_style=TravelStyle.CULTURE,
        travel_pace=TravelPace.MEDIUM,
        budget_tier=BudgetTier.MID_RANGE,
    )
    await pref_repo.save(existing)

    query = GetNearbyRecommendationsQuery(
        user_id=str(FIXED_USER_UUID),
        latitude=48.8566,
        longitude=2.3522,
        radius_meters=10000,
        limit=5,
    )

    result = await service.get_nearby_recommendations(query)
    assert isinstance(result, Success)
    assert len(result.value) == 1
    assert result.value[0].title == "Eiffel Tower"
    assert result.value[0].metadata["country_code"] == "FR"


@pytest.mark.asyncio
async def test_get_similar_trips_success() -> None:
    """get_similar_trips should verify trip exists and query similarity engine."""
    service, _, trip_repo, _ = _make_service()

    # Save trip
    trip = Trip(
        entity_id=TripId(value=FIXED_TRIP_UUID),
        owner_id=UserId(value=FIXED_USER_UUID),
        title=TripTitle(value="My Trip"),
        status=TripStatus.DRAFT,
        privacy=TripPrivacy.PRIVATE,
        date_range=None,
    )
    await trip_repo.save(trip)

    query = GetSimilarTripsQuery(trip_id=str(FIXED_TRIP_UUID), limit=5)
    result = await service.get_similar_trips(query)
    assert isinstance(result, Success)
    assert len(result.value) == 1
    assert result.value[0].title == "Historical Kyoto Explorer"
