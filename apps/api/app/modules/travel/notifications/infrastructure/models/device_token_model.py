"""DevicePushTokenModel ORM definition."""

from __future__ import annotations

import uuid
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class DevicePushTokenModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for user device push tokens."""

    __tablename__ = "user_device_push_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    token: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        unique=True,
        index=True,
        sort_order=2,
    )

    platform: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="expo",
        sort_order=3,
    )

    device_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        sort_order=4,
    )

    __table_args__ = (
        Index(
            "ix_user_device_push_tokens_user_id_platform",
            "user_id",
            "platform",
        ),
    )
