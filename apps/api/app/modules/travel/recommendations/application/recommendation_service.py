"""RecommendationService orchestrating preferences and queries."""

from __future__ import annotations

import logging
from uuid import UUID

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.locations.repository import LocationRepository
from app.modules.travel.recommendations.application.commands import UpdatePreferencesCommand
from app.modules.travel.recommendations.application.dtos import (
    GetNearbyRecommendationsResult,
    GetRecommendationsResult,
    GetSimilarTripsResult,
    GetTrendingDestinationsResult,
    RecommendationDTO,
    RecommendationsListDTO,
    SimilarTripDTO,
    UpdatePreferencesResult,
    UserPreferencesDTO,
)
from app.modules.travel.recommendations.application.queries import (
    GetNearbyRecommendationsQuery,
    GetRecommendationsQuery,
    GetSimilarTripsQuery,
    GetTrendingDestinationsQuery,
)
from app.modules.travel.recommendations.domain.entities.recommendation import (
    DestinationRecommendation,
)
from app.modules.travel.recommendations.domain.entities.user_preferences import UserPreferences
from app.modules.travel.recommendations.domain.enums.budget_tier import BudgetTier
from app.modules.travel.recommendations.domain.enums.travel_pace import TravelPace
from app.modules.travel.recommendations.domain.enums.travel_style import TravelStyle
from app.modules.travel.recommendations.domain.errors import UserPreferencesNotFoundError
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
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import ValidationError
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.result import Failure, Result, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider

logger = logging.getLogger(__name__)


class RecommendationService:
    """Orchestrates all use cases for user preferences and recommendations."""

    def __init__(
        self,
        *,
        preferences_repository: IUserPreferencesRepository,
        trip_repository: ITripRepository,
        location_repository: LocationRepository,
        recommendation_engine: RecommendationEngine,
        similarity_engine: SimilarityEngine,
        popularity_provider: PopularityProvider,
        uow: UnitOfWork,
        uuid_provider: UUIDProvider,
        event_publisher: EventPublisher,
    ) -> None:
        self._preferences_repository = preferences_repository
        self._trip_repository = trip_repository
        self._location_repository = location_repository
        self._recommendation_engine = recommendation_engine
        self._similarity_engine = similarity_engine
        self._popularity_provider = popularity_provider
        self._uow = uow
        self._uuid_provider = uuid_provider
        self._event_publisher = event_publisher

    async def update_preferences(
        self, command: UpdatePreferencesCommand
    ) -> UpdatePreferencesResult:
        """Create or update travel preferences for a user."""
        try:
            uid = UserId(value=UUID(command.user_id))
        except ValueError:
            return Failure(ValidationError(f"Invalid user_id: {command.user_id}", field="user_id"))

        try:
            interests = [InterestTag(value=t) for t in command.interests]
            dietary = [DietaryTag(value=t) for t in command.dietary_preferences]
            style = TravelStyle(command.travel_style.lower())
            pace = TravelPace(command.travel_pace.lower())
            budget = BudgetTier(command.budget_tier.lower())
        except ValidationError as exc:
            return Failure(exc)
        except ValueError as exc:
            return Failure(ValidationError(f"Invalid preference value: {exc}", field="preferences"))

        async with self._uow:
            preferences = await self._preferences_repository.find_by_user_id(uid)
            if preferences is None:
                pid = PreferencesId(value=self._uuid_provider.generate())
                preferences = UserPreferences.create(
                    preferences_id=pid,
                    user_id=uid,
                    interests=interests,
                    dietary_preferences=dietary,
                    travel_style=style,
                    travel_pace=pace,
                    budget_tier=budget,
                )
            else:
                preferences.update(
                    interests=interests,
                    dietary_preferences=dietary,
                    travel_style=style,
                    travel_pace=pace,
                    budget_tier=budget,
                )

            await self._preferences_repository.save(preferences)
            await self._uow.commit()

        # Publish domain events
        for event in preferences.pop_events():
            await self._event_publisher.publish(event)

        return Success(UserPreferencesDTO.from_entity(preferences))

    async def get_preferences(self, user_id: str) -> Result[UserPreferencesDTO]:
        """Fetch travel preferences for a user."""
        try:
            uid = UserId(value=UUID(user_id))
        except ValueError:
            return Failure(ValidationError(f"Invalid user_id: {user_id}", field="user_id"))

        async with self._uow:
            preferences = await self._preferences_repository.find_by_user_id(uid)
            if preferences is None:
                return Failure(UserPreferencesNotFoundError(user_id))
            return Success(UserPreferencesDTO.from_entity(preferences))

    async def get_recommendations(self, query: GetRecommendationsQuery) -> GetRecommendationsResult:
        """Generate personalized recommendations for destinations, activities, and restaurants."""
        try:
            uid = UserId(value=UUID(query.user_id))
        except ValueError:
            return Failure(ValidationError(f"Invalid user_id: {query.user_id}", field="user_id"))

        trip_uuid: UUID | None = None
        if query.trip_id:
            try:
                trip_uuid = UUID(query.trip_id)
            except ValueError:
                return Failure(
                    ValidationError(f"Invalid trip_id: {query.trip_id}", field="trip_id")
                )

        async with self._uow:
            # 1. Fetch preferences
            preferences = await self._preferences_repository.find_by_user_id(uid)
            if preferences is None:
                return Failure(UserPreferencesNotFoundError(query.user_id))

            # 2. Verify trip exists if provided
            if trip_uuid:
                trip = await self._trip_repository.find_by_id(TripId(value=trip_uuid))
                if trip is None or getattr(trip, "deleted_at", None) is not None:
                    return Failure(
                        ValidationError(f"Trip '{query.trip_id}' not found.", field="trip_id")
                    )

            # 3. Call engines
            dest_recs = await self._recommendation_engine.recommend_destinations(
                preferences, limit=query.limit
            )

            act_recs = []
            rest_recs = []
            if trip_uuid:
                act_recs = await self._recommendation_engine.recommend_activities(
                    preferences, trip_id=trip_uuid, limit=query.limit
                )
                rest_recs = await self._recommendation_engine.recommend_restaurants(
                    preferences, trip_id=trip_uuid, limit=query.limit
                )

            # 4. Group results
            dto = RecommendationsListDTO(
                destinations=[RecommendationDTO.from_entity(r) for r in dest_recs],
                activities=[RecommendationDTO.from_entity(r) for r in act_recs],
                restaurants=[RecommendationDTO.from_entity(r) for r in rest_recs],
            )
            return Success(dto)

    async def get_trending_destinations(
        self, query: GetTrendingDestinationsQuery
    ) -> GetTrendingDestinationsResult:
        """Fetch trending destinations."""
        async with self._uow:
            recs = await self._popularity_provider.get_popular_destinations(limit=query.limit)
            return Success([RecommendationDTO.from_entity(r) for r in recs])

    async def get_nearby_recommendations(
        self, query: GetNearbyRecommendationsQuery
    ) -> GetNearbyRecommendationsResult:
        """Fetch nearby recommendations utilizing LocationRepository's geo queries."""
        try:
            uid = UserId(value=UUID(query.user_id))
        except ValueError:
            return Failure(ValidationError(f"Invalid user_id: {query.user_id}", field="user_id"))

        async with self._uow:
            # Check preferences exist
            preferences = await self._preferences_repository.find_by_user_id(uid)
            if preferences is None:
                return Failure(UserPreferencesNotFoundError(query.user_id))

            # Execute PostGIS query via location repo
            locations = await self._location_repository.find_nearby(
                latitude=query.latitude,
                longitude=query.longitude,
                radius_meters=query.radius_meters,
                limit=query.limit,
            )

            # Map locations to DestinationRecommendation entities
            # Assigning mock relevance score and custom reason
            recs = []
            for loc in locations:
                recs.append(
                    DestinationRecommendation(
                        entity_id=loc.id,
                        title=loc.name,
                        description=loc.description,
                        score=RecommendationScore(value=85),
                        reason=RecommendationReason(
                            value=f"Close to your specified location ({loc.locality or 'nearby'})."
                        ),
                        location_id=loc.id,
                        country_code=loc.country_code,
                    )
                )

            return Success([RecommendationDTO.from_entity(r) for r in recs])

    async def get_similar_trips(self, query: GetSimilarTripsQuery) -> GetSimilarTripsResult:
        """Fetch list of similar trips."""
        try:
            tid = UUID(query.trip_id)
        except ValueError:
            return Failure(ValidationError(f"Invalid trip_id: {query.trip_id}", field="trip_id"))

        async with self._uow:
            trip = await self._trip_repository.find_by_id(TripId(value=tid))
            if trip is None or getattr(trip, "deleted_at", None) is not None:
                return Failure(
                    ValidationError(f"Trip '{query.trip_id}' not found.", field="trip_id")
                )

            raw_sims = await self._similarity_engine.find_similar_trips(tid, limit=query.limit)
            dtos = []
            for item in raw_sims:
                dtos.append(
                    SimilarTripDTO(
                        trip_id=str(item["trip_id"]),
                        title=str(item["title"]),
                        score=int(item["score"]),
                        reason=str(item["reason"]),
                    )
                )

            return Success(dtos)
