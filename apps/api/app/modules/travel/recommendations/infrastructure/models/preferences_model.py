"""SQLAlchemy model for UserPreferences."""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.mixins import (
    OptimisticLockMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class UserPreferencesModel(
    Base,
    UUIDPrimaryKeyMixin,
    OptimisticLockMixin,
    TimestampMixin,
):
    """ORM representation of UserPreferences."""

    __tablename__ = "user_preferences"

    user_id: Mapped[PG_UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )
    interests: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
    )
    dietary_preferences: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
    )
    travel_style: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="culture",
        server_default="culture",
    )
    travel_pace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    budget_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="mid_range",
        server_default="mid_range",
    )
