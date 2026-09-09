"""Unit tests for GeminiPlanningEngine and real-place grounding."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.config import get_settings
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.services.ai.factory import get_planning_engine
from app.services.ai.gemini import GeminiPlanningEngine
from app.services.ai.mock import MockPlanningEngine
from app.services.maps.mock import MockPlacesProvider
from app.shared.domain.errors import ExternalServiceError


@pytest.fixture
def sample_preferences() -> PlanningPreferences:
    return PlanningPreferences(
        destination="Rome",
        duration_days=2,
        budget_level="mid_range",
        interests=("history", "food"),
        travel_style="balanced",
        special_requirements="None",
    )


@pytest.mark.asyncio
async def test_gemini_planning_engine_grounding_success(
    sample_preferences: PlanningPreferences,
) -> None:
    # Places provider pre-seeded with Colosseum and Trattoria Da Enzo
    places_provider = MockPlacesProvider()

    # Simulated AI response referencing Colosseum and Trattoria Da Enzo
    fake_ai_plan = {
        "summary": "A 2-day historical and culinary journey through Rome.",
        "estimated_total_cost": "$250",
        "days": [
            {
                "day_number": 1,
                "title": "Day 1 — Ancient Rome",
                "description": "Step back into the Roman Empire.",
                "activities": [
                    {
                        "title": "Tour the Ancient Amphitheater",
                        "description": "Walk through the historic arches.",
                        "category": "sightseeing",
                        "duration_minutes": 180,
                        "estimated_cost": "$25",
                        "place_name": "Colosseum",
                    }
                ],
            },
            {
                "day_number": 2,
                "title": "Day 2 — Roman Cuisine",
                "description": "Taste local authentic dishes.",
                "activities": [
                    {
                        "title": "Authentic Lunch in Trastevere",
                        "description": "Savor traditional carbonara.",
                        "category": "dining",
                        "duration_minutes": 90,
                        "estimated_cost": "$35",
                        "place_name": "Trattoria Da Enzo al 29",
                    }
                ],
            },
        ],
    }

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(fake_ai_plan)}]}}]
    }
    mock_client.post.return_value = mock_resp

    engine = GeminiPlanningEngine(
        api_key="fake-gemini-key",
        places_provider=places_provider,
        http_client=mock_client,
    )

    result = await engine.generate_plan(sample_preferences)

    # Validate high level plan
    assert result.summary == "A 2-day historical and culinary journey through Rome."
    assert len(result.days) == 2

    # Verify Day 1 activity was GROUNDED using verified Places provider coordinates
    day1_act = result.days[0].activities[0]
    assert day1_act.is_verified is True
    assert day1_act.provider_place_id == "mock_place_colosseum"
    assert day1_act.place_name == "Colosseum"
    assert day1_act.formatted_address == "Piazza del Colosseo, 1, 00184 Roma RM, Italy"
    assert day1_act.latitude == 41.890210
    assert day1_act.longitude == 12.492231
    assert day1_act.rating == 4.7

    # Verify Day 2 activity was GROUNDED
    day2_act = result.days[1].activities[0]
    assert day2_act.is_verified is True
    assert day2_act.provider_place_id == "mock_place_trattoria_enzo"
    assert day2_act.place_name == "Trattoria Da Enzo al 29"
    assert day2_act.latitude == 41.887550
    assert day2_act.longitude == 12.477280


@pytest.mark.asyncio
async def test_gemini_hallucinated_place_rejection(
    sample_preferences: PlanningPreferences,
) -> None:
    # Places provider with only Colosseum (no fictional places)
    places_provider = MockPlacesProvider()

    # AI suggests 1 real place (Colosseum) and 1 completely fictional place ("Underwater Atlantis Temple of Rome")
    fake_ai_plan = {
        "summary": "A 1-day exploration.",
        "days": [
            {
                "day_number": 1,
                "title": "Day 1 — Exploration",
                "description": "Testing hallucination rejection.",
                "activities": [
                    {
                        "title": "Real Place",
                        "description": "Exploring Colosseum",
                        "category": "sightseeing",
                        "duration_minutes": 120,
                        "place_name": "Colosseum",
                    },
                    {
                        "title": "Fictional Spot",
                        "description": "A completely invented fake temple that doesn't exist",
                        "category": "sightseeing",
                        "duration_minutes": 60,
                        "place_name": "Underwater Atlantis Temple of Rome Nonexistent Fictional",
                    },
                ],
            }
        ],
    }

    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(fake_ai_plan)}]}}]
    }
    mock_client.post.return_value = mock_resp

    engine = GeminiPlanningEngine(
        api_key="fake-gemini-key",
        places_provider=places_provider,
        http_client=mock_client,
    )

    result = await engine.generate_plan(sample_preferences)

    # Hallucinated activity MUST be dropped! Only the verified Colosseum activity remains.
    assert len(result.days[0].activities) == 1
    assert result.days[0].activities[0].place_name == "Colosseum"
    assert result.days[0].activities[0].provider_place_id == "mock_place_colosseum"


@pytest.mark.asyncio
async def test_gemini_malformed_json_response(
    sample_preferences: PlanningPreferences,
) -> None:
    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "THIS IS NOT VALID JSON {[[["}]}}]
    }
    mock_client.post.return_value = mock_resp

    engine = GeminiPlanningEngine(
        api_key="fake-gemini-key",
        places_provider=MockPlacesProvider(),
        http_client=mock_client,
    )

    with pytest.raises(ExternalServiceError) as exc_info:
        await engine.generate_plan(sample_preferences)
    assert "malformed JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_gemini_rate_limit_and_timeout(
    sample_preferences: PlanningPreferences,
) -> None:
    # Test 429 quota error
    mock_client_429 = AsyncMock()
    mock_client_429.is_closed = False
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_client_429.post.return_value = mock_resp_429

    engine_429 = GeminiPlanningEngine(
        api_key="fake-gemini-key",
        places_provider=MockPlacesProvider(),
        http_client=mock_client_429,
    )

    with pytest.raises(ExternalServiceError) as exc_info_429:
        await engine_429.generate_plan(sample_preferences)
    assert "quota or rate limit exceeded" in str(exc_info_429.value)

    # Test timeout
    mock_client_timeout = AsyncMock()
    mock_client_timeout.is_closed = False
    mock_client_timeout.post.side_effect = httpx.TimeoutException("Read timed out")

    engine_timeout = GeminiPlanningEngine(
        api_key="fake-gemini-key",
        places_provider=MockPlacesProvider(),
        max_retries=1,
        http_client=mock_client_timeout,
    )

    with pytest.raises(ExternalServiceError) as exc_info_timeout:
        await engine_timeout.generate_plan(sample_preferences)
    assert "unavailable" in str(exc_info_timeout.value)


def test_ai_factory_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()

    # Default is mock
    engine = get_planning_engine()
    assert isinstance(engine, MockPlanningEngine)

    # When configured for gemini
    monkeypatch.setenv("AI_PROVIDER", "gemini")
    monkeypatch.setenv("AI_API_KEY", "real-gemini-key-12345")
    get_settings.cache_clear()

    gemini_engine = get_planning_engine()
    assert isinstance(gemini_engine, GeminiPlanningEngine)

    get_settings.cache_clear()
