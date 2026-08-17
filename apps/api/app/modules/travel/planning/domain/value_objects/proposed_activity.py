"""ProposedActivity — a single activity within a proposed day."""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ProposedActivity(ValueObject):
    """
    An individual activity suggested by the AI planning engine.

    Immutable value object. Part of a ProposedDay which is part of a
    PlanningResult. Contains no identity — defined entirely by attributes.

    Attributes:
        title:            Activity name (e.g. "Visit the Colosseum").
        description:      Brief explanation of the activity.
        category:         Activity category (e.g. sightseeing, dining, transport).
        duration_minutes: Estimated duration in minutes.
        estimated_cost:   Optional cost estimate as a formatted string (e.g. "$25").
    """

    title: str
    description: str
    category: str
    duration_minutes: int
    estimated_cost: str | None = None
