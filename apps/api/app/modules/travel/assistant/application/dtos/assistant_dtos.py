"""Assistant Application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.travel.assistant.domain.enums import (
    ActionStatus,
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.budget.application.dtos import BudgetSummary, ExpenseSummary
from app.modules.travel.itinerary.application.dtos import ItinerarySummary


@dataclass(frozen=True)
class ChatMessageDTO:
    role: str
    content: str
    timestamp: datetime | None = None


@dataclass(frozen=True)
class PersistedMessageDTO:
    message_id: UUID
    role: str
    content: str
    response_type: AssistantResponseType | None
    action_id: UUID | None
    tools_used: tuple[AssistantActionType, ...]
    created_at: datetime


@dataclass(frozen=True)
class ConversationHistoryDTO:
    conversation_id: UUID
    trip_id: UUID
    user_id: UUID
    messages: tuple[PersistedMessageDTO, ...]


@dataclass(frozen=True)
class ProposedActionDTO:
    action_id: UUID
    trip_id: UUID
    action_type: AssistantActionType
    summary: str
    description: str
    payload: dict[str, Any]
    status: ActionStatus
    created_at: datetime
    applied_at: datetime | None = None


@dataclass(frozen=True)
class ChatResponseDTO:
    message: str
    response_type: AssistantResponseType
    proposed_action: ProposedActionDTO | None = None
    tools_used: tuple[AssistantActionType, ...] = ()


@dataclass(frozen=True)
class ConfirmActionResultDTO:
    action: ProposedActionDTO
    itinerary: ItinerarySummary | None = None
    expense: ExpenseSummary | None = None
    budget: BudgetSummary | None = None
    message: str = "Action applied successfully."


@dataclass(frozen=True)
class RejectActionResultDTO:
    action: ProposedActionDTO
    message: str = "Action cancelled."


@dataclass(frozen=True)
class TravelWarningDTO:
    warning_id: str
    category: str
    severity: str
    title: str
    message: str
    day_number: int | None = None
    item_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@dataclass(frozen=True)
class TripWarningsDTO:
    trip_id: UUID
    warnings: tuple[TravelWarningDTO, ...]
    total_warnings: int
    has_critical: bool
    itinerary_conflicts_count: int
    budget_risks_count: int
