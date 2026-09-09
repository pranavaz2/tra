"""Assistant Domain Value Objects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.modules.travel.assistant.domain.value_objects.travel_warning import (
    TravelWarning,
)
from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ActionId(ValueObject):
    """Unique identifier for a proposed assistant action."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_str(cls, value: str) -> ActionId:
        return cls(value=UUID(value))


@dataclass(frozen=True)
class ConversationId(ValueObject):
    """Unique identifier for an assistant conversation session."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_str(cls, value: str) -> ConversationId:
        return cls(value=UUID(value))


@dataclass(frozen=True)
class MessageId(ValueObject):
    """Unique identifier for a persisted assistant message."""

    value: UUID

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_str(cls, value: str) -> MessageId:
        return cls(value=UUID(value))


@dataclass(frozen=True)
class ChatMessage(ValueObject):
    """A single turn in the assistant chat session."""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = datetime.now(UTC)


__all__ = [
    "ActionId",
    "ChatMessage",
    "ConversationId",
    "MessageId",
    "TravelWarning",
]
