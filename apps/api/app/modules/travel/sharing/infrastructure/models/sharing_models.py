"""TripCollaboration ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
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


class TripCollaborationModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """ORM model for trip_collaborations table."""

    __tablename__ = "trip_collaborations"

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

    is_public: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        sort_order=3,
    )

    share_token: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        unique=True,
        index=True,
        sort_order=4,
    )

    members: Mapped[list[TripMemberModel]] = relationship(
        "TripMemberModel",
        back_populates="collaboration",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="TripMemberModel.joined_at",
    )

    invitations: Mapped[list[InvitationModel]] = relationship(
        "InvitationModel",
        back_populates="collaboration",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="InvitationModel.created_at.desc()",
    )

    @declared_attr.directive  # type: ignore[override]
    def __mapper_args__(self) -> dict[str, Any]:
        return {"version_id_col": self.__table__.c.version}

    __table_args__ = (
        Index(
            "ix_trip_collaborations_owner_id_active",
            "owner_id",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class TripMemberModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for trip_members table."""

    __tablename__ = "trip_members"

    collaboration_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trip_collaborations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        sort_order=2,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        sort_order=3,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        sort_order=4,
    )

    collaboration: Mapped[TripCollaborationModel] = relationship(
        "TripCollaborationModel",
        back_populates="members",
    )

    __table_args__ = (
        UniqueConstraint(
            "collaboration_id",
            "user_id",
            name="uq_trip_members_collaboration_user",
        ),
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_trip_members_role",
        ),
    )


class InvitationModel(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """ORM model for trip_invitations table."""

    __tablename__ = "trip_invitations"

    collaboration_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trip_collaborations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    invitee_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        sort_order=2,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        sort_order=3,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
        sort_order=4,
    )

    token: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        unique=True,
        index=True,
        sort_order=5,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        sort_order=6,
    )

    collaboration: Mapped[TripCollaborationModel] = relationship(
        "TripCollaborationModel",
        back_populates="invitations",
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_trip_invitations_role",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')",
            name="ck_trip_invitations_status",
        ),
        Index(
            "ix_trip_invitations_collaboration_email_pending",
            "collaboration_id",
            "invitee_email",
            postgresql_where=text("status = 'pending'"),
        ),
    )
