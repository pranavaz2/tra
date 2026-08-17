"""Infrastructure Layer — Dependency Injection Containers for Recommendations."""

from __future__ import annotations

import logging
from functools import lru_cache
from types import TracebackType
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DatabaseSession
from app.modules.identity.authentication.infrastructure.event_publisher import (
    LoggingEventPublisher,
)
from app.modules.locations.repository import LocationRepository
from app.modules.travel.recommendations.application.handlers import (
    GetNearbyRecommendationsHandler,
    GetRecommendationsHandler,
    GetSimilarTripsHandler,
    GetTrendingDestinationsHandler,
    UpdatePreferencesHandler,
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
from app.modules.travel.recommendations.domain.repositories.interfaces import (
    IUserPreferencesRepository,
)
from app.modules.travel.recommendations.domain.services.interfaces import (
    PopularityProvider,
    RankingEngine,
    RecommendationEngine,
    SimilarityEngine,
)
from app.modules.travel.recommendations.domain.value_objects.recommendation_reason import (
    RecommendationReason,
)
from app.modules.travel.recommendations.domain.value_objects.recommendation_score import (
    RecommendationScore,
)
from app.modules.travel.recommendations.infrastructure.repositories.preferences_repository import (
    SQLAlchemyUserPreferencesRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import CurrentTripRepository
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Stub Providers (For local compilation/dev)                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class StubRecommendationEngine:
    """Stub RecommendationEngine implementation."""

    async def recommend_destinations(
        self,
        preferences: UserPreferences,
        limit: int = 10,
    ) -> list[DestinationRecommendation]:
        tags = [t.value for t in preferences.interests]
        recs = []

        if "culture" in tags or not tags:
            recs.append(
                DestinationRecommendation(
                    entity_id=UUID("11111111-1111-1111-1111-111111111111"),
                    title="Kyoto, Japan",
                    description="Historic temples and gardens.",
                    score=RecommendationScore(value=95),
                    reason=RecommendationReason(value="Highly relevant to your culture interest."),
                    location_id=UUID("11111111-1111-1111-1111-111111111111"),
                    country_code="JP",
                )
            )

        if "adventure" in tags or not tags:
            recs.append(
                DestinationRecommendation(
                    entity_id=UUID("22222222-2222-2222-2222-222222222222"),
                    title="Queenstown, New Zealand",
                    description="Adventure capital of the world.",
                    score=RecommendationScore(value=90),
                    reason=RecommendationReason(
                        value="Matches your travel style and interest in adventure."
                    ),
                    location_id=UUID("22222222-2222-2222-2222-222222222222"),
                    country_code="NZ",
                )
            )

        if not recs:
            recs.append(
                DestinationRecommendation(
                    entity_id=UUID("33333333-3333-3333-3333-333333333333"),
                    title="Paris, France",
                    description="City of light, art, and fashion.",
                    score=RecommendationScore(value=85),
                    reason=RecommendationReason(
                        value=f"Great match for your {preferences.budget_tier.value} budget."
                    ),
                    location_id=UUID("33333333-3333-3333-3333-333333333333"),
                    country_code="FR",
                )
            )

        return recs[:limit]

    async def recommend_activities(
        self,
        preferences: UserPreferences,
        trip_id: UUID,
        limit: int = 10,
    ) -> list[ActivityRecommendation]:
        return [
            ActivityRecommendation(
                entity_id=UUID("44444444-4444-4444-4444-444444444444"),
                title="Historical Walking Tour",
                description="Tour of local landmarks and historic areas.",
                score=RecommendationScore(value=92),
                reason=RecommendationReason(
                    value="Aligned with your travel pace (medium) and style."
                ),
                activity_type="Sightseeing",
                trip_id=trip_id,
            )
        ][:limit]

    async def recommend_restaurants(
        self,
        preferences: UserPreferences,
        trip_id: UUID,
        limit: int = 10,
    ) -> list[RestaurantRecommendation]:
        return [
            RestaurantRecommendation(
                entity_id=UUID("55555555-5555-5555-5555-555555555555"),
                title="The Green Sprout",
                description="A highly rated organic eatery.",
                score=RecommendationScore(value=88),
                reason=RecommendationReason(value="Matches your dietary tags."),
                cuisine_type="Vegetarian",
                trip_id=trip_id,
            )
        ][:limit]


class StubSimilarityEngine:
    """Stub SimilarityEngine implementation."""

    async def find_similar_trips(
        self,
        trip_id: UUID,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return [
            {
                "trip_id": UUID("99999999-9999-9999-9999-999999999999"),
                "title": "Summer in Tokyo & Kyoto",
                "score": 90,
                "reason": "Uses similar destinations and itinerary items.",
            }
        ][:limit]


class StubRankingEngine:
    """Stub RankingEngine implementation."""

    async def rank_items(
        self,
        items: list[Any],
        preferences: UserPreferences,
    ) -> list[Any]:
        # Trivial pass-through or sort based on score attribute if exists
        try:
            return sorted(items, key=lambda x: getattr(x, "score", 0), reverse=True)
        except Exception:
            return items


class StubPopularityProvider:
    """Stub PopularityProvider implementation."""

    async def get_popular_destinations(
        self,
        limit: int = 10,
    ) -> list[DestinationRecommendation]:
        return [
            DestinationRecommendation(
                entity_id=UUID("66666666-6666-6666-6666-666666666666"),
                title="Rome, Italy",
                description="The eternal city of history and ancient monuments.",
                score=RecommendationScore(value=98),
                reason=RecommendationReason(value="Trending globally with high ratings."),
                location_id=UUID("66666666-6666-6666-6666-666666666666"),
                country_code="IT",
            )
        ][:limit]


# ──────────────────────────────────────────────────────────────────────────── #
# Session-bound Unit of Work                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class _SessionBoundUnitOfWork:
    """UnitOfWork wrapping request-scoped AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> _SessionBoundUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self._session.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


# ──────────────────────────────────────────────────────────────────────────── #
# Dependency Providers                                                           #
# ──────────────────────────────────────────────────────────────────────────── #


@lru_cache(maxsize=1)
def _build_recommendation_event_publisher() -> LoggingEventPublisher:
    return LoggingEventPublisher()


def get_recommendation_event_publisher() -> EventPublisher:
    return _build_recommendation_event_publisher()


@lru_cache(maxsize=1)
def _build_recommendation_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_recommendation_uuid_provider() -> UUIDProvider:
    return _build_recommendation_uuid_provider()


@lru_cache(maxsize=1)
def get_recommendation_engine() -> RecommendationEngine:
    return StubRecommendationEngine()


@lru_cache(maxsize=1)
def get_similarity_engine() -> SimilarityEngine:
    return StubSimilarityEngine()


@lru_cache(maxsize=1)
def get_ranking_engine() -> RankingEngine:
    return StubRankingEngine()


@lru_cache(maxsize=1)
def get_popularity_provider() -> PopularityProvider:
    return StubPopularityProvider()


# Annotated dependencies
CurrentRecEventPublisher = Annotated[EventPublisher, Depends(get_recommendation_event_publisher)]
CurrentRecUUIDProvider = Annotated[UUIDProvider, Depends(get_recommendation_uuid_provider)]
CurrentRecEngine = Annotated[RecommendationEngine, Depends(get_recommendation_engine)]
CurrentSimilarityEngine = Annotated[SimilarityEngine, Depends(get_similarity_engine)]
CurrentRankingEngine = Annotated[RankingEngine, Depends(get_ranking_engine)]
CurrentPopularityProvider = Annotated[PopularityProvider, Depends(get_popularity_provider)]


# Per-request dependencies
def get_user_preferences_repository(db: DatabaseSession) -> IUserPreferencesRepository:
    return SQLAlchemyUserPreferencesRepository(db)


def get_recommendations_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    return _SessionBoundUnitOfWork(db)


def get_location_repository(db: DatabaseSession) -> LocationRepository:
    return LocationRepository(db)


CurrentUserPreferencesRepository = Annotated[
    IUserPreferencesRepository, Depends(get_user_preferences_repository)
]
CurrentRecommendationsUnitOfWork = Annotated[UnitOfWork, Depends(get_recommendations_unit_of_work)]
CurrentLocationRepository = Annotated[LocationRepository, Depends(get_location_repository)]


# ──────────────────────────────────────────────────────────────────────────── #
# Service & Handlers                                                             #
# ──────────────────────────────────────────────────────────────────────────── #


def get_recommendation_service(
    preferences_repository: CurrentUserPreferencesRepository,
    trip_repository: CurrentTripRepository,
    location_repository: CurrentLocationRepository,
    recommendation_engine: CurrentRecEngine,
    similarity_engine: CurrentSimilarityEngine,
    popularity_provider: CurrentPopularityProvider,
    uow: CurrentRecommendationsUnitOfWork,
    uuid_provider: CurrentRecUUIDProvider,
    event_publisher: CurrentRecEventPublisher,
) -> RecommendationService:
    return RecommendationService(
        preferences_repository=preferences_repository,
        trip_repository=trip_repository,
        location_repository=location_repository,
        recommendation_engine=recommendation_engine,
        similarity_engine=similarity_engine,
        popularity_provider=popularity_provider,
        uow=uow,
        uuid_provider=uuid_provider,
        event_publisher=event_publisher,
    )


CurrentRecommendationService = Annotated[RecommendationService, Depends(get_recommendation_service)]


def get_update_preferences_handler(
    service: CurrentRecommendationService,
) -> UpdatePreferencesHandler:
    return UpdatePreferencesHandler(service)


def get_get_recommendations_handler(
    service: CurrentRecommendationService,
) -> GetRecommendationsHandler:
    return GetRecommendationsHandler(service)


def get_get_trending_destinations_handler(
    service: CurrentRecommendationService,
) -> GetTrendingDestinationsHandler:
    return GetTrendingDestinationsHandler(service)


def get_get_nearby_recommendations_handler(
    service: CurrentRecommendationService,
) -> GetNearbyRecommendationsHandler:
    return GetNearbyRecommendationsHandler(service)


def get_get_similar_trips_handler(
    service: CurrentRecommendationService,
) -> GetSimilarTripsHandler:
    return GetSimilarTripsHandler(service)


CurrentUpdatePreferencesHandler = Annotated[
    UpdatePreferencesHandler, Depends(get_update_preferences_handler)
]
CurrentGetRecommendationsHandler = Annotated[
    GetRecommendationsHandler, Depends(get_get_recommendations_handler)
]
CurrentGetTrendingDestinationsHandler = Annotated[
    GetTrendingDestinationsHandler, Depends(get_get_trending_destinations_handler)
]
CurrentGetNearbyRecommendationsHandler = Annotated[
    GetNearbyRecommendationsHandler, Depends(get_get_nearby_recommendations_handler)
]
CurrentGetSimilarTripsHandler = Annotated[
    GetSimilarTripsHandler, Depends(get_get_similar_trips_handler)
]
