"""Recommendations Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.recommendations.application.commands import UpdatePreferencesCommand
from app.modules.travel.recommendations.application.queries import (
    GetNearbyRecommendationsQuery,
    GetRecommendationsQuery,
    GetSimilarTripsQuery,
    GetTrendingDestinationsQuery,
)
from app.modules.travel.recommendations.infrastructure.dependencies import (
    CurrentGetNearbyRecommendationsHandler,
    CurrentGetRecommendationsHandler,
    CurrentGetSimilarTripsHandler,
    CurrentGetTrendingDestinationsHandler,
    CurrentRecommendationService,
    CurrentUpdatePreferencesHandler,
)
from app.modules.travel.recommendations.presentation.error_responses import (
    map_recommendation_failure,
)
from app.modules.travel.recommendations.presentation.schemas import (
    DataEnvelope,
    RecommendationResponse,
    RecommendationsResponse,
    SimilarTripResponse,
    UpdatePreferencesRequest,
    UserPreferencesResponse,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recommendations & Preferences"])


# ──────────────────────────────────────────────────────────────────────────── #
# Preferences Endpoints                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/preferences",
    response_model=DataEnvelope[UserPreferencesResponse],
    status_code=status.HTTP_200_OK,
    summary="Update user travel preferences",
    operation_id="updatePreferences",
)
async def update_preferences(
    request: UpdatePreferencesRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdatePreferencesHandler,
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = "/api/v1/preferences"

    command = UpdatePreferencesCommand(
        user_id=str(auth.user_id),
        interests=request.interests,
        dietary_preferences=request.dietary_preferences,
        travel_style=request.travel_style,
        travel_pace=request.travel_pace,
        budget_tier=request.budget_tier,
    )

    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_recommendation_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=dto):
            envelope = DataEnvelope(data=UserPreferencesResponse.model_validate(dto))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


@router.get(
    "/preferences",
    response_model=DataEnvelope[UserPreferencesResponse],
    status_code=status.HTTP_200_OK,
    summary="Get user travel preferences",
    operation_id="getPreferences",
)
async def get_preferences(
    auth: RequireAuthentication,
    service: CurrentRecommendationService,
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = "/api/v1/preferences"

    result = await service.get_preferences(str(auth.user_id))

    match result:
        case Failure(error=err):
            return map_recommendation_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=dto):
            envelope = DataEnvelope(data=UserPreferencesResponse.model_validate(dto))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# Recommendations Endpoints                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/recommendations",
    response_model=DataEnvelope[RecommendationsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get personalized travel recommendations",
    operation_id="getRecommendations",
)
async def get_recommendations(
    auth: RequireAuthentication,
    handler: CurrentGetRecommendationsHandler,
    trip_id: str | None = Query(None, description="Optional trip ID context"),
    limit: int = Query(10, ge=1, le=50, description="Max recommendations to return"),
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = "/api/v1/recommendations"

    query = GetRecommendationsQuery(
        user_id=str(auth.user_id),
        trip_id=trip_id,
        limit=limit,
    )

    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_recommendation_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=dto):
            envelope = DataEnvelope(data=RecommendationsResponse.model_validate(dto))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


@router.get(
    "/recommendations/trending",
    response_model=DataEnvelope[list[RecommendationResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get globally trending destinations",
    operation_id="getTrendingDestinations",
)
async def get_trending_destinations(
    auth: RequireAuthentication,
    handler: CurrentGetTrendingDestinationsHandler,
    limit: int = Query(10, ge=1, le=50, description="Max trending items to return"),
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = "/api/v1/recommendations/trending"

    query = GetTrendingDestinationsQuery(limit=limit)
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_recommendation_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=dtos):
            envelope = DataEnvelope(data=[RecommendationResponse.model_validate(d) for d in dtos])
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


@router.get(
    "/recommendations/nearby",
    response_model=DataEnvelope[list[RecommendationResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get nearby recommendations",
    operation_id="getNearbyRecommendations",
)
async def get_nearby_recommendations(
    auth: RequireAuthentication,
    handler: CurrentGetNearbyRecommendationsHandler,
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate"),
    radius_meters: int = Query(50000, ge=1, description="Radius in meters"),
    limit: int = Query(10, ge=1, le=50, description="Max recommendations to return"),
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = "/api/v1/recommendations/nearby"

    query = GetNearbyRecommendationsQuery(
        user_id=str(auth.user_id),
        latitude=latitude,
        longitude=longitude,
        radius_meters=radius_meters,
        limit=limit,
    )

    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_recommendation_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=dtos):
            envelope = DataEnvelope(data=[RecommendationResponse.model_validate(d) for d in dtos])
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


@router.get(
    "/recommendations/similar",
    response_model=DataEnvelope[list[SimilarTripResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get similar trips based on an existing trip",
    operation_id="getSimilarTrips",
)
async def get_similar_trips(
    auth: RequireAuthentication,
    handler: CurrentGetSimilarTripsHandler,
    trip_id: str = Query(..., description="Trip ID context"),
    limit: int = Query(10, ge=1, le=50, description="Max similar trips to return"),
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = "/api/v1/recommendations/similar"

    query = GetSimilarTripsQuery(trip_id=trip_id, limit=limit)
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_recommendation_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=dtos):
            envelope = DataEnvelope(data=[SimilarTripResponse.model_validate(d) for d in dtos])
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )
