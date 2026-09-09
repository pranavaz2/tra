"""AssistantConversation Repository Interface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.domain.entities.conversation import (
    AssistantConversation,
)
from app.modules.travel.assistant.domain.value_objects import ConversationId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


@runtime_checkable
class IAssistantConversationRepository(Protocol):
    """Persistence interface for AssistantConversation aggregates."""

    async def find_by_id(
        self, conversation_id: ConversationId
    ) -> AssistantConversation | None:
        """Find conversation by unique ID."""
        ...

    async def find_by_trip_and_user(
        self, trip_id: TripId, user_id: UserId
    ) -> AssistantConversation | None:
        """Find active conversation for a given trip and user."""
        ...

    async def save(self, conversation: AssistantConversation) -> None:
        """Persist or update conversation aggregate and its messages."""
        ...

    async def delete(self, conversation_id: ConversationId) -> None:
        """Delete conversation."""
        ...
