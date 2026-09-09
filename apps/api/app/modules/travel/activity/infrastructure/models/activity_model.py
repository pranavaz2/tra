"""TripActivityModel ORM definition."""

from __future__ import annotations

from typing import Any
import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.database import Base


class TripActivityModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for the trip_activity_logs table."""

    __tablename__ = "trip_activity_logs"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    actor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        sort_order=2,
    )

    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        sort_order=3,
    )

    entity_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        sort_order=4,
    )

    entity_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        sort_order=5,
    )

    title: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        sort_order=6,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        sort_order=7,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        sort_order=8,
    )

    __table_args__ = (
        Index(
            "ix_trip_activity_logs_trip_id_created_at",
            "trip_id",
            "created_at",
        ),
    )
