"""Assistant Application Commands and Queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.modules.travel.assistant.domain.value_objects import ChatMessage


@dataclass(frozen=True)
class ChatCommand:
    trip_id: str
    requester_id: str
    message: str
    history: list[ChatMessage] | None = None


@dataclass(frozen=True)
class ConfirmActionCommand:
    trip_id: str
    action_id: str
    requester_id: str


@dataclass(frozen=True)
class RejectActionCommand:
    trip_id: str
    action_id: str
    requester_id: str


@dataclass(frozen=True)
class GetHistoryQuery:
    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class ClearHistoryCommand:
    trip_id: str
    requester_id: str
