"""TravelWarning Domain Value Object."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.travel.assistant.domain.enums import WarningCategory, WarningSeverity
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class TravelWarning(ValueObject):
    """Represents a proactive warning regarding itinerary feasibility, schedule conflicts, or budget risk."""

    warning_id: str
    category: WarningCategory
    severity: WarningSeverity
    title: str
    message: str
    day_number: int | None = None
    item_ids: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
