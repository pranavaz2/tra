"""SQLAlchemy ORM models for Itineraries, Days, and Items."""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.core.db.mixins import (
    OptimisticLockMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class ItineraryModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """ORM model for the itineraries table."""

    __tablename__ = "itineraries"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Trip that owns this itinerary.",
        sort_order=1,
    )

    # Relationship to Days
    days: Mapped[list[ItineraryDayModel]] = relationship(
        "ItineraryDayModel",
        back_populates="itinerary",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="ItineraryDayModel.day_number",
    )

    @declared_attr.directive  # type: ignore[override]
    def __mapper_args__(cls) -> dict:  # type: ignore[override]  # noqa: N805
        return {"version_id_col": cls.__table__.c.version}

    def __repr__(self) -> str:
        return f"ItineraryModel(id={self.id!r}, trip_id={self.trip_id!r})"


class ItineraryDayModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for the itinerary_days table."""

    __tablename__ = "itinerary_days"

    itinerary_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("itineraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Itinerary that owns this day.",
        sort_order=1,
    )

    day_number: Mapped[int] = mapped_column(
        nullable=False,
        comment="Sequential day index (1-based).",
        sort_order=2,
    )

    title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional descriptive name for this day.",
        sort_order=3,
    )

    date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Specific calendar date for this day.",
        sort_order=4,
    )

    # Relationships
    itinerary: Mapped[ItineraryModel] = relationship("ItineraryModel", back_populates="days")
    items: Mapped[list[ItineraryItemModel]] = relationship(
        "ItineraryItemModel",
        back_populates="day",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="ItineraryItemModel.start_time.nullslast(), ItineraryItemModel.id",
    )

    __table_args__ = (
        UniqueConstraint(
            "itinerary_id",
            "day_number",
            name="uq_itinerary_days_itinerary_day_number",
        ),
        CheckConstraint(
            "day_number >= 1",
            name="ck_itinerary_days_day_number",
        ),
    )

    def __repr__(self) -> str:
        return f"ItineraryDayModel(id={self.id!r}, day_number={self.day_number!r})"


class ItineraryItemModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for the itinerary_items table."""

    __tablename__ = "itinerary_items"

    day_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("itinerary_days.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Day that contains this item.",
        sort_order=1,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Brief description of this activity.",
        sort_order=2,
    )

    item_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Category of this item: activity | transport | lodging | restaurant",
        sort_order=3,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed notes, links, or instructions.",
        sort_order=4,
    )

    start_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="Scheduled start time of this item.",
        sort_order=5,
    )

    end_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
        comment="Scheduled end time of this item.",
        sort_order=6,
    )

    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional canonical location from the locations catalog.",
        sort_order=7,
    )

    cost: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Estimated cost for this item.",
        sort_order=8,
    )

    currency: Mapped[str | None] = mapped_column(
        String(3),
        nullable=True,
        comment="Three-letter ISO currency code.",
        sort_order=9,
    )

    # Relationships
    day: Mapped[ItineraryDayModel] = relationship("ItineraryDayModel", back_populates="items")

    __table_args__ = (
        CheckConstraint(
            "item_type IN ('activity', 'transport', 'lodging', 'restaurant')",
            name="ck_itinerary_items_item_type",
        ),
    )

    def __repr__(self) -> str:
        return f"ItineraryItemModel(id={self.id!r}, title={self.title!r}, type={self.item_type!r})"
