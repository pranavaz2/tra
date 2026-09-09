"""Assistant Conversation and Message SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.mixins import (
    OptimisticLockMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class AssistantConversationModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """ORM model for assistant_conversations table."""

    __tablename__ = "assistant_conversations"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    messages: Mapped[list[AssistantMessageModel]] = relationship(
        "AssistantMessageModel",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="AssistantMessageModel.created_at.asc()",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("trip_id", "user_id", name="uq_assistant_conversation_trip_user"),
        Index("ix_assistant_conv_trip_user", "trip_id", "user_id"),
    )


class AssistantMessageModel(UUIDPrimaryKeyMixin, Base):
    """ORM model for assistant_messages table."""

    __tablename__ = "assistant_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    response_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    tools_used: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        index=True,
    )

    conversation: Mapped[AssistantConversationModel] = relationship(
        "AssistantConversationModel",
        back_populates="messages",
    )
