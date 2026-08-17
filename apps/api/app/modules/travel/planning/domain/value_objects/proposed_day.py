"""ProposedDay — a single day within an AI-generated travel plan."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.travel.planning.domain.value_objects.proposed_activity import (
    ProposedActivity,
)
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ProposedDay(ValueObject):
    """
    A single day within an AI-generated travel plan.

    Immutable value object. Contains a sequence of proposed activities
    ordered by suggested execution time.

    Attributes:
        day_number:  1-based day index within the plan.
        title:       Human-readable day title (e.g. "Day 1 — Exploring Rome").
        description: Brief summary of the day's plan.
        activities:  Ordered tuple of proposed activities for this day.
    """

    day_number: int
    title: str
    description: str
    activities: tuple[ProposedActivity, ...]
