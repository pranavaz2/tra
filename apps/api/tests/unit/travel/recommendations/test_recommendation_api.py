"""API endpoint tests for the travel recommendations router using stub handlers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.core.security.auth.errors import AuthorizationError
from app.modules.travel.recommendations.application.dtos import (
    RecommendationDTO,
    RecommendationsListDTO,
    SimilarTripDTO,
    UserPreferencesDTO,
)
from app.modules.travel.recommendations.domain.errors import UserPreferencesNotFoundError
from app.modules.travel.recommendations.infrastructure.dependencies import (
    get_get_nearby_recommendations_handler,
    get_get_recommendations_handler,
    get_get_similar_trips_handler,
    get_get_trending_destinations_handler,
    get_recommendation_service,
    get_update_preferences_handler,
)
from app.modules.travel.recommendations.presentation.router import router
from app.shared.domain.result import Failure, Success

# ─────────────────────────────────────────────────────────────────────────────
# Shared constants & fixtures
# ─────────────────────────────────────────────────────────────────────────────

USER_ID = str(uuid.uuid4())
TRIP_ID = str(uuid.uuid4())
REC_ID = str(uuid.uuid4())


def _auth_ctx() -> AuthorizationContext:
    now = datetime.now(UTC)
    return AuthorizationContext(
        user_id=USER_ID,
        session_id=str(uuid.uuid4()),
        token_id=str(uuid.uuid4()),
        token_version=1,
        session_version=1,
        authentication_method="password",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        email="test@example.com",
        is_email_verified=True,
    )


def _make_preferences_dto() -> UserPreferencesDTO:
    return UserPreferencesDTO(
        user_id=USER_ID,
        interests=["culture", "food"],
        dietary_preferences=["vegan"],
        travel_style="food",
        travel_pace="medium",
        budget_tier="mid_range",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Stub Handlers & Service Mock
# ─────────────────────────────────────────────────────────────────────────────


class _StubHandler:
    def __init__(self, result: object) -> None:
        self._result = result

    async def handle(self, message: object) -> object:
        return self._result


class _MockRecommendationService:
    def __init__(self, pref_result: object) -> None:
        self._pref_result = pref_result

    async def get_preferences(self, user_id: str) -> object:
        return self._pref_result


# ─────────────────────────────────────────────────────────────────────────────
# App factory
# ─────────────────────────────────────────────────────────────────────────────


async def _auth_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
    return exc.to_response()


def _make_app(
    *,
    update_pref_result: object | None = None,
    get_pref_result: object | None = None,
    get_recs_result: object | None = None,
    get_trending_result: object | None = None,
    get_nearby_result: object | None = None,
    get_similar_result: object | None = None,
    authenticated: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(AuthorizationError, _auth_error_handler)  # type: ignore[arg-type]
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(router)
    app.include_router(api_v1)

    if authenticated:
        app.dependency_overrides[get_authorization_context] = _auth_ctx

    if update_pref_result is not None:
        app.dependency_overrides[get_update_preferences_handler] = lambda: _StubHandler(update_pref_result)
    if get_pref_result is not None:
        app.dependency_overrides[get_recommendation_service] = lambda: _MockRecommendationService(get_pref_result)
    if get_recs_result is not None:
        app.dependency_overrides[get_get_recommendations_handler] = lambda: _StubHandler(get_recs_result)
    if get_trending_result is not None:
        app.dependency_overrides[get_get_trending_destinations_handler] = lambda: _StubHandler(get_trending_result)
    if get_nearby_result is not None:
        app.dependency_overrides[get_get_nearby_recommendations_handler] = lambda: _StubHandler(get_nearby_result)
    if get_similar_result is not None:
        app.dependency_overrides[get_get_similar_trips_handler] = lambda: _StubHandler(get_similar_result)

    return app


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_preferences_endpoint_success() -> None:
    expected = _make_preferences_dto()
    app = _make_app(update_pref_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/api/v1/preferences",
            json={
                "interests": ["culture", "food"],
                "dietary_preferences": ["vegan"],
                "travel_style": "food",
                "travel_pace": "medium",
                "budget_tier": "mid_range",
            },
        )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["user_id"] == USER_ID
    assert json_data["data"]["interests"] == ["culture", "food"]


@pytest.mark.asyncio
async def test_get_preferences_endpoint_success() -> None:
    expected = _make_preferences_dto()
    app = _make_app(get_pref_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/preferences")

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["data"]["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_get_preferences_endpoint_not_found() -> None:
    app = _make_app(get_pref_result=Failure(UserPreferencesNotFoundError(USER_ID)))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/preferences")

    assert response.status_code == 404
    json_data = response.json()
    assert json_data["error_code"] == "USER_PREFERENCES_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_recommendations_endpoint_success() -> None:
    expected = RecommendationsListDTO(
        destinations=[
            RecommendationDTO(
                id=REC_ID,
                title="Kyoto, Japan",
                description="Gardens and history.",
                score=95,
                reason="Culture matched.",
                recommendation_type="destination",
                metadata={"location_id": str(uuid.uuid4()), "country_code": "JP"},
            )
        ],
        activities=[],
        restaurants=[],
    )
    app = _make_app(get_recs_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recommendations?trip_id=" + TRIP_ID)

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]["destinations"]) == 1
    assert json_data["data"]["destinations"][0]["title"] == "Kyoto, Japan"


@pytest.mark.asyncio
async def test_get_trending_destinations_endpoint_success() -> None:
    expected = [
        RecommendationDTO(
            id=REC_ID,
            title="Rome, Italy",
            description=None,
            score=98,
            reason="Popular choice.",
            recommendation_type="destination",
            metadata={"country_code": "IT"},
        )
    ]
    app = _make_app(get_trending_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recommendations/trending?limit=5")

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]) == 1
    assert json_data["data"][0]["title"] == "Rome, Italy"


@pytest.mark.asyncio
async def test_get_nearby_recommendations_endpoint_success() -> None:
    expected = [
        RecommendationDTO(
            id=REC_ID,
            title="Eiffel Tower",
            description="Tower.",
            score=88,
            reason="Nearby.",
            recommendation_type="destination",
            metadata={"country_code": "FR"},
        )
    ]
    app = _make_app(get_nearby_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/recommendations/nearby?latitude=48.8566&longitude=2.3522&radius_meters=10000"
        )

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]) == 1
    assert json_data["data"][0]["title"] == "Eiffel Tower"


@pytest.mark.asyncio
async def test_get_similar_trips_endpoint_success() -> None:
    expected = [
        SimilarTripDTO(
            trip_id=TRIP_ID,
            title="Historical Kyoto",
            score=90,
            reason="Culture match.",
        )
    ]
    app = _make_app(get_similar_result=Success(expected))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/recommendations/similar?trip_id=" + TRIP_ID)

    assert response.status_code == 200
    json_data = response.json()
    assert len(json_data["data"]) == 1
    assert json_data["data"][0]["title"] == "Historical Kyoto"
