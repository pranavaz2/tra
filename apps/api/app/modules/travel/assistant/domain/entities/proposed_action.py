"""ProposedAction Entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.modules.travel.assistant.domain.enums import ActionStatus, AssistantActionType
from app.modules.travel.assistant.domain.errors import ActionAlreadyExecutedError
from app.modules.travel.assistant.domain.value_objects import ActionId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot


@dataclass(kw_only=True, eq=False)
class ProposedAction(AggregateRoot[ActionId]):
    """
    Represents an AI-generated structured mutation that requires user confirmation.

    Invariants:
      - Can only transition from PENDING -> APPLIED or PENDING -> REJECTED.
      - Never directly mutates DB. Must be applied through application services.
    """

    trip_id: TripId
    action_type: AssistantActionType
    summary: str
    description: str
    payload: dict[str, Any]
    status: ActionStatus = ActionStatus.PENDING
    applied_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        action_id: ActionId,
        trip_id: TripId,
        action_type: AssistantActionType,
        summary: str,
        description: str,
        payload: dict[str, Any],
    ) -> ProposedAction:
        return cls(
            entity_id=action_id,
            trip_id=trip_id,
            action_type=action_type,
            summary=summary,
            description=description,
            payload=payload,
            status=ActionStatus.PENDING,
        )

    def mark_applied(self) -> None:
        if self.status != ActionStatus.PENDING:
            raise ActionAlreadyExecutedError(str(self.entity_id), self.status.value)
        self.status = ActionStatus.APPLIED
        self.applied_at = datetime.now(UTC)

    def mark_rejected(self) -> None:
        if self.status != ActionStatus.PENDING:
            raise ActionAlreadyExecutedError(str(self.entity_id), self.status.value)
        self.status = ActionStatus.REJECTED
