"""
MockPlanningEngine — deterministic AI plan generator for testing.

Returns a fixed 3-day travel plan regardless of input preferences.
No external API key is required. This implementation is used for:
  - Unit and integration tests
  - Local development without a live AI provider
  - CI/CD pipeline validation

The mock generates plausible structure (days, activities, costs) so
downstream consumers (Itinerary creation, UI rendering) can be tested
end-to-end without a live AI service.

Per CLAUDE.md §4.7: "A MockAIProvider must exist for local development
and testing — no developer should need a live AI API key to build features."
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)
from app.modules.travel.planning.domain.value_objects.proposed_activity import (
    ProposedActivity,
)
from app.modules.travel.planning.domain.value_objects.proposed_day import ProposedDay


class MockPlanningEngine:
    """
    Deterministic mock AI planning engine.

    Always returns a 3-day plan with 2 activities per day, using the
    destination from the provided preferences. Thread-safe and stateless.
    """

    async def generate_plan(
        self, preferences: PlanningPreferences
    ) -> PlanningResult:
        """Generate a deterministic mock travel plan."""
        destination = preferences.destination
        duration = min(preferences.duration_days, 3)

        days: list[ProposedDay] = []
        for day_num in range(1, duration + 1):
            activities = (
                ProposedActivity(
                    title=f"Morning exploration in {destination}",
                    description=f"Explore the highlights of {destination} on day {day_num}.",
                    category="sightseeing",
                    duration_minutes=180,
                    estimated_cost="$25",
                ),
                ProposedActivity(
                    title=f"Local cuisine experience in {destination}",
                    description=f"Enjoy authentic local food in {destination}.",
                    category="dining",
                    duration_minutes=120,
                    estimated_cost="$40",
                ),
            )
            days.append(
                ProposedDay(
                    day_number=day_num,
                    title=f"Day {day_num} — Discovering {destination}",
                    description=(
                        f"A full day of exploration and local "
                        f"experiences in {destination}."
                    ),
                    activities=activities,
                )
            )

        return PlanningResult(
            summary=(
                f"A {duration}-day {preferences.travel_style} trip to {destination} "
                f"with a {preferences.budget_level} budget."
            ),
            days=tuple(days),
            estimated_total_cost=f"${duration * 65}",
            generated_at=datetime.now(UTC),
        )
