"""TripMediaCollection and MediaItem ORM models."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.core.db.mixins import (
    OptimisticLockMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class TripMediaCollectionModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """ORM model for the trip_media_collections table."""

    __tablename__ = "trip_media_collections"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        sort_order=1,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        sort_order=2,
    )

    # Relationships
    items: Mapped[list[MediaItemModel]] = relationship(
        "MediaItemModel",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MediaItemModel.created_at.desc()",
    )

    @declared_attr.directive  # type: ignore[override]
    def __mapper_args__(self) -> dict[str, Any]:
        return {"version_id_col": self.__table__.c.version}

    __table_args__ = (
        Index(
            "ix_trip_media_collections_owner_id_active",
            "owner_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class MediaItemModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for the media_items table."""

    __tablename__ = "media_items"

    collection_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trip_media_collections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        sort_order=2,
    )

    media_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        sort_order=3,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        sort_order=4,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        sort_order=5,
    )

    caption: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        sort_order=6,
    )

    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        sort_order=7,
    )

    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("itinerary_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        sort_order=8,
    )

    expense_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        sort_order=9,
    )

    # Relationships
    collection: Mapped[TripMediaCollectionModel] = relationship(
        "TripMediaCollectionModel",
        back_populates="items",
    )

    __table_args__ = (
        Index(
            "ix_media_items_collection_id_created_at",
            "collection_id",
            "created_at",
        ),
    )
