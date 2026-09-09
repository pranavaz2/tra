"""SQLAlchemy ORM model for user notification preferences."""

from __future__ import annotations

from datetime import UTC, datetime, time
import uuid

from sqlalchemy import Boolean, DateTime, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NotificationPreferencesModel(Base):
    """SQLAlchemy model for user-level notification preferences."""

    __tablename__ = "notification_preferences"

    preference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        index=True,
    )
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trip_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    itinerary_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    collaboration: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    budget_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    travel_warnings: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weather_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quiet_hours_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[time | None] = mapped_column(Time, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
