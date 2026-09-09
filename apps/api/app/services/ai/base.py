"""
PlanningEngine — AI service interface for travel plan generation.

This Protocol defines the domain-level contract for generating travel plans.
The interface deliberately avoids any provider-specific concepts (model names,
token counts, API versions, prompt templates) per CLAUDE.md §4.7.

Implementations:
  - MockPlanningEngine (mock.py): deterministic, no API key needed.
  - Future: OpenAIPlanningEngine, AnthropicPlanningEngine, etc.

All feature modules import PlanningEngine from this package. They never
import provider SDKs directly (CLAUDE.md §4.6, §12).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.modules.travel.planning.domain.value_objects.planning_preferences import (
        PlanningPreferences,
    )
    from app.modules.travel.planning.domain.value_objects.planning_result import (
        PlanningResult,
    )


@runtime_checkable
class PlanningEngine(Protocol):
    """
    AI-powered travel plan generator.

    Accepts structured planning preferences and returns a structured
    planning result. The implementation is responsible for:
      - Constructing provider-specific prompts (never leaked to callers).
      - Parsing provider responses into the PlanningResult domain type.
      - Handling provider-specific errors and retries internally.

    Failures raise ExternalServiceError (from app.shared.domain.errors).
    """

    async def generate_plan(self, preferences: PlanningPreferences) -> PlanningResult:
        """
        Generate a travel plan based on user preferences.

        Args:
            preferences: Structured planning preferences (destination,
                         duration, budget, interests, travel style).

        Returns:
            A PlanningResult containing the proposed itinerary.

        Raises:
            ExternalServiceError: If the AI provider fails after retries.
        """
        ...
