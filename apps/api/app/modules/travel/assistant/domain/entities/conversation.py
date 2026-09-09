"""AssistantConversation Aggregate Root and AssistantMessage Entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.domain.enums import (
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.domain.value_objects import (
    ActionId,
    ConversationId,
    MessageId,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class AssistantMessage(Entity[MessageId]):
    """A single persisted chat message within an assistant conversation."""

    role: str  # "user" | "assistant" | "system"
    content: str
    response_type: AssistantResponseType | None = None
    action_id: ActionId | None = None
    tools_used: tuple[AssistantActionType, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(kw_only=True, eq=False)
class AssistantConversation(AggregateRoot[ConversationId]):
    """
    AssistantConversation aggregate root.

    Manages persistent multi-turn conversational history scoped to a single trip and user.
    """

    trip_id: TripId
    user_id: UserId
    messages: list[AssistantMessage] = field(default_factory=list)
    version: int = 1
    deleted_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        conversation_id: ConversationId,
        trip_id: TripId,
        user_id: UserId,
    ) -> AssistantConversation:
        return cls(
            entity_id=conversation_id,
            trip_id=trip_id,
            user_id=user_id,
            messages=[],
            version=1,
        )

    def add_user_message(
        self,
        *,
        message_id: MessageId,
        content: str,
    ) -> AssistantMessage:
        """Append a new user message to the conversation."""
        msg = AssistantMessage(
            entity_id=message_id,
            role="user",
            content=content.strip(),
            created_at=datetime.now(UTC),
        )
        self.messages.append(msg)
        self.version += 1
        self.touch()
        return msg

    def add_assistant_message(
        self,
        *,
        message_id: MessageId,
        content: str,
        response_type: AssistantResponseType = AssistantResponseType.INFORMATIONAL,
        action_id: ActionId | None = None,
        tools_used: tuple[AssistantActionType, ...] = (),
    ) -> AssistantMessage:
        """Append a structured assistant response message to the conversation."""
        msg = AssistantMessage(
            entity_id=message_id,
            role="assistant",
            content=content,
            response_type=response_type,
            action_id=action_id,
            tools_used=tools_used,
            created_at=datetime.now(UTC),
        )
        self.messages.append(msg)
        self.version += 1
        self.touch()
        return msg

    def get_bounded_history(self, limit: int = 10) -> list[AssistantMessage]:
        """Return the most recent N messages to avoid context window blowup."""
        if not self.messages:
            return []
        return self.messages[-limit:]

    def clear_messages(self) -> None:
        """Clear conversation history."""
        self.messages.clear()
        self.version += 1
        self.touch()
