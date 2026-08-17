"""PlanningResult — structured output from the AI planning engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.travel.planning.domain.value_objects.proposed_day import ProposedDay
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class PlanningResult(ValueObject):
    """
    The complete result of an AI plan generation.

    Immutable value object wrapping the AI engine's output in a
    domain-friendly structure. Stored as part of the TripProposal
    aggregate when the proposal transitions to READY.

    Attributes:
        summary:              Human-readable summary of the generated plan.
        days:                 Ordered tuple of proposed days.
        estimated_total_cost: Optional total cost estimate as a formatted string.
        generated_at:         UTC timestamp of when the plan was generated.
    """

    summary: str
    days: tuple[ProposedDay, ...]
    estimated_total_cost: str | None
    generated_at: datetime
