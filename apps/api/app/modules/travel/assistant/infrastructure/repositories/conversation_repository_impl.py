"""Assistant Conversation Repository Implementations (SQLAlchemy & In-Memory)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.domain.entities.conversation import (
    AssistantConversation,
    AssistantMessage,
)
from app.modules.travel.assistant.domain.enums import (
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.domain.repositories.conversation_repository import (
    IAssistantConversationRepository,
)
from app.modules.travel.assistant.domain.value_objects import (
    ActionId,
    ConversationId,
    MessageId,
)
from app.modules.travel.assistant.infrastructure.models.conversation_model import (
    AssistantConversationModel,
    AssistantMessageModel,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId

logger = logging.getLogger(__name__)


class InMemoryAssistantConversationRepository(IAssistantConversationRepository):
    """In-memory conversation repository for unit tests and local execution."""

    def __init__(self) -> None:
        self._conversations: dict[str, AssistantConversation] = {}
        self._lock = asyncio.Lock()

    async def find_by_id(
        self, conversation_id: ConversationId
    ) -> AssistantConversation | None:
        async with self._lock:
            conv = self._conversations.get(str(conversation_id))
            if conv and conv.deleted_at is None:
                return conv
            return None

    async def find_by_trip_and_user(
        self, trip_id: TripId, user_id: UserId
    ) -> AssistantConversation | None:
        async with self._lock:
            for conv in self._conversations.values():
                if (
                    conv.trip_id == trip_id
                    and conv.user_id == user_id
                    and conv.deleted_at is None
                ):
                    return conv
            return None

    async def save(self, conversation: AssistantConversation) -> None:
        async with self._lock:
            self._conversations[str(conversation.entity_id)] = conversation

    async def delete(self, conversation_id: ConversationId) -> None:
        async with self._lock:
            if str(conversation_id) in self._conversations:
                del self._conversations[str(conversation_id)]


class SQLAlchemyAssistantConversationRepository(IAssistantConversationRepository):
    """PostgreSQL SQLAlchemy repository for AssistantConversation aggregate."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(
        self, conversation_id: ConversationId
    ) -> AssistantConversation | None:
        stmt = (
            select(AssistantConversationModel)
            .where(
                and_(
                    AssistantConversationModel.id == conversation_id.value,
                    AssistantConversationModel.deleted_at.is_(None),
                )
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_aggregate(model)

    async def find_by_trip_and_user(
        self, trip_id: TripId, user_id: UserId
    ) -> AssistantConversation | None:
        stmt = (
            select(AssistantConversationModel)
            .where(
                and_(
                    AssistantConversationModel.trip_id == trip_id.value,
                    AssistantConversationModel.user_id == user_id.value,
                    AssistantConversationModel.deleted_at.is_(None),
                )
            )
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_aggregate(model)

    async def save(self, conversation: AssistantConversation) -> None:
        stmt = select(AssistantConversationModel).where(
            AssistantConversationModel.id == conversation.entity_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = AssistantConversationModel(
                id=conversation.entity_id.value,
                trip_id=conversation.trip_id.value,
                user_id=conversation.user_id.value,
                version=conversation.version,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
                deleted_at=conversation.deleted_at,
            )
            self._session.add(model)
        else:
            model.version = conversation.version
            model.updated_at = conversation.updated_at
            model.deleted_at = conversation.deleted_at

        # Synchronize messages
        existing_msg_ids = {m.id for m in model.messages}
        for domain_msg in conversation.messages:
            if domain_msg.entity_id.value not in existing_msg_ids:
                msg_model = AssistantMessageModel(
                    id=domain_msg.entity_id.value,
                    conversation_id=conversation.entity_id.value,
                    role=domain_msg.role,
                    content=domain_msg.content,
                    response_type=domain_msg.response_type.value if domain_msg.response_type else None,
                    action_id=domain_msg.action_id.value if domain_msg.action_id else None,
                    tools_used=[t.value for t in domain_msg.tools_used],
                    created_at=domain_msg.created_at,
                )
                model.messages.append(msg_model)

        await self._session.flush()

    async def delete(self, conversation_id: ConversationId) -> None:
        stmt = select(AssistantConversationModel).where(
            AssistantConversationModel.id == conversation_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)
            await self._session.flush()

    def _to_aggregate(self, model: AssistantConversationModel) -> AssistantConversation:
        messages = []
        for msg_model in model.messages:
            tools_used = tuple(
                AssistantActionType(t)
                for t in (msg_model.tools_used or [])
                if t in AssistantActionType._value2member_map_
            )
            resp_type = (
                AssistantResponseType(msg_model.response_type)
                if msg_model.response_type in AssistantResponseType._value2member_map_
                else None
            )
            action_id = ActionId(value=msg_model.action_id) if msg_model.action_id else None

            messages.append(
                AssistantMessage(
                    entity_id=MessageId(value=msg_model.id),
                    role=msg_model.role,
                    content=msg_model.content,
                    response_type=resp_type,
                    action_id=action_id,
                    tools_used=tools_used,
                    created_at=msg_model.created_at,
                )
            )

        conv = AssistantConversation(
            entity_id=ConversationId(value=model.id),
            trip_id=TripId(value=model.trip_id),
            user_id=UserId(value=model.user_id),
            messages=messages,
            version=model.version,
            deleted_at=model.deleted_at,
        )
        return conv
