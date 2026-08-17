"""Recommendations CQRS command and query handlers."""

from __future__ import annotations

import logging

from app.modules.travel.recommendations.application.commands import UpdatePreferencesCommand
from app.modules.travel.recommendations.application.dtos import (
    GetNearbyRecommendationsResult,
    GetRecommendationsResult,
    GetSimilarTripsResult,
    GetTrendingDestinationsResult,
    UpdatePreferencesResult,
)
from app.modules.travel.recommendations.application.queries import (
    GetNearbyRecommendationsQuery,
    GetRecommendationsQuery,
    GetSimilarTripsQuery,
    GetTrendingDestinationsQuery,
)
from app.modules.travel.recommendations.application.recommendation_service import (
    RecommendationService,
)

logger = logging.getLogger(__name__)


class UpdatePreferencesHandler:
    """CQRS handler for UpdatePreferencesCommand."""

    def __init__(self, service: RecommendationService) -> None:
        self._service = service

    async def handle(self, command: UpdatePreferencesCommand) -> UpdatePreferencesResult:
        logger.debug(
            "Handling UpdatePreferencesCommand",
            extra={"user_id": command.user_id},
        )
        return await self._service.update_preferences(command)


class GetRecommendationsHandler:
    """CQRS handler for GetRecommendationsQuery."""

    def __init__(self, service: RecommendationService) -> None:
        self._service = service

    async def handle(self, query: GetRecommendationsQuery) -> GetRecommendationsResult:
        logger.debug(
            "Handling GetRecommendationsQuery",
            extra={"user_id": query.user_id, "trip_id": query.trip_id},
        )
        return await self._service.get_recommendations(query)


class GetTrendingDestinationsHandler:
    """CQRS handler for GetTrendingDestinationsQuery."""

    def __init__(self, service: RecommendationService) -> None:
        self._service = service

    async def handle(self, query: GetTrendingDestinationsQuery) -> GetTrendingDestinationsResult:
        logger.debug(
            "Handling GetTrendingDestinationsQuery",
            extra={"limit": query.limit},
        )
        return await self._service.get_trending_destinations(query)


class GetNearbyRecommendationsHandler:
    """CQRS handler for GetNearbyRecommendationsQuery."""

    def __init__(self, service: RecommendationService) -> None:
        self._service = service

    async def handle(self, query: GetNearbyRecommendationsQuery) -> GetNearbyRecommendationsResult:
        logger.debug(
            "Handling GetNearbyRecommendationsQuery",
            extra={"user_id": query.user_id, "lat": query.latitude, "lon": query.longitude},
        )
        return await self._service.get_nearby_recommendations(query)


class GetSimilarTripsHandler:
    """CQRS handler for GetSimilarTripsQuery."""

    def __init__(self, service: RecommendationService) -> None:
        self._service = service

    async def handle(self, query: GetSimilarTripsQuery) -> GetSimilarTripsResult:
        logger.debug(
            "Handling GetSimilarTripsQuery",
            extra={"trip_id": query.trip_id},
        )
        return await self._service.get_similar_trips(query)
