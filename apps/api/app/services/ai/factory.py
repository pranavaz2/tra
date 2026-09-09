"""
AI provider factory — selects the concrete PlanningEngine implementation.

Reads the AI_PROVIDER setting and returns the matching implementation.
Default is MockPlanningEngine for local development and testing.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.services.ai.base import PlanningEngine
from app.services.ai.gemini import GeminiPlanningEngine
from app.services.ai.mock import MockPlanningEngine
from app.services.maps.factory import get_places_provider

logger = logging.getLogger(__name__)


def get_planning_engine() -> PlanningEngine:
    """
    Return the active PlanningEngine implementation.

    Selects GeminiPlanningEngine when AI_PROVIDER is 'gemini',
    otherwise returns MockPlanningEngine.
    """
    settings = get_settings()

    if settings.ai_provider == "gemini":
        key = settings.gemini_api_key or settings.ai_api_key
        if key:
            places_provider = get_places_provider()
            engine = GeminiPlanningEngine(
                api_key=key.get_secret_value(),
                places_provider=places_provider,
                model=settings.ai_model or "gemini-2.0-flash",
                timeout_seconds=float(settings.ai_timeout_seconds),
                temperature=float(settings.ai_temperature),
                max_output_tokens=settings.ai_max_tokens,
                max_retries=settings.ai_max_retries,
            )
            logger.info(
                "PlanningEngine: GeminiPlanningEngine active (model=%s, places_provider=%s)",
                settings.ai_model or "gemini-2.0-flash",
                settings.places_provider,
            )
            return engine
        else:
            logger.warning(
                "PlanningEngine: AI_PROVIDER=gemini but no API key found — falling back to MockPlanningEngine."
            )

    logger.info("PlanningEngine: MockPlanningEngine active (set AI_PROVIDER=gemini to use real AI).")
    return MockPlanningEngine()
