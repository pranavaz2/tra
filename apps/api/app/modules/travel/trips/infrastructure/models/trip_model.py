"""
TripModel — SQLAlchemy ORM model for the trips table.

Maps the Trip aggregate to PostgreSQL. This module contains only the
persistence representation. Business logic lives in the domain entity;
mapping between ORM model and domain entity is the repository's concern.

Table: trips

Column order (driven by sort_order):
  id            (sort_order=-100, UUIDPrimaryKeyMixin)
  owner_id      (sort_order=1)
  title         (sort_order=2)
  status        (sort_order=3)
  privacy       (sort_order=4)
  departure_date (sort_order=5)
  return_date   (sort_order=6)
  is_date_flexible (sort_order=7)
  created_at    (sort_order=98,  TimestampMixin)
  updated_at    (sort_order=99,  TimestampMixin)
  deleted_at    (sort_order=100, SoftDeleteMixin)
  version       (sort_order=101, OptimisticLockMixin)

Optimistic locking:
  SQLAlchemy tracks the version column via __mapper_args__. On every ORM
  UPDATE it increments version and raises StaleDataError if the stored
  version no longer matches the session value (concurrent-write detection).

Soft delete:
  deleted_at IS NULL is the live-record invariant. All repository list
  queries must call exclude_deleted() from app.core.db.query.

Status and privacy:
  Stored as VARCHAR(20) with CHECK constraints. PostgreSQL native ENUM types
  are avoided because ALTER TYPE to add values requires an exclusive lock
  and cannot run inside a transaction.

Foreign key — owner_id → users.id:
  ON DELETE RESTRICT prevents orphaned trips if a user record is hard-deleted.
  In normal operation users are soft-deleted, so this constraint never fires.
  The users table must exist before the trips migration runs.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.core.db.mixins import (
    OptimisticLockMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class TripModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """
    ORM model for the trips table.

    Inherits:
        id          — UUID v4 primary key (UUIDPrimaryKeyMixin)
        created_at  — timestamp with timezone (TimestampMixin)
        updated_at  — timestamp with timezone, auto-updates (TimestampMixin)
        deleted_at  — nullable timestamp for soft delete (SoftDeleteMixin)
        version     — integer for optimistic concurrency (OptimisticLockMixin)
    """

    __tablename__ = "trips"

    # ---------------------------------------------------------------------- #
    # Business columns                                                         #
    # ---------------------------------------------------------------------- #

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="User who created and owns this trip.",
        sort_order=1,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Stripped trip name. 1–100 characters.",
        sort_order=2,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'draft'"),
        comment="Trip lifecycle status. See TripStatus domain enum for valid values.",
        sort_order=3,
    )

    privacy: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'private'"),
        comment="Visibility setting. See TripPrivacy domain enum for valid values.",
        sort_order=4,
    )

    # TripDateRange is flattened into three columns.
    # NULL departure_date means no travel dates have been set yet (DRAFT state).
    departure_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="First day of the trip. NULL when no dates are scheduled.",
        sort_order=5,
    )

    return_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Last day of the trip. NULL for open-ended trips or unscheduled trips.",
        sort_order=6,
    )

    is_date_flexible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="True when the user has not committed to exact travel dates.",
        sort_order=7,
    )

    # ---------------------------------------------------------------------- #
    # Optimistic locking                                                       #
    # ---------------------------------------------------------------------- #

    # version is declared in OptimisticLockMixin. __mapper_args__ below wires
    # SQLAlchemy's version tracking to the column defined in the mixin.
    # declared_attr.directive defers resolution until __table__ is fully built,
    # giving us a real Column object (required by version_id_col).

    @declared_attr.directive  # type: ignore[override]
    def __mapper_args__(cls) -> dict:  # type: ignore[override]
        return {"version_id_col": cls.__table__.c.version}

    # ---------------------------------------------------------------------- #
    # Indexes and constraints                                                  #
    # ---------------------------------------------------------------------- #

    __table_args__ = (
        # Composite index: the most common query path — list trips by owner
        # filtered by status. Covers "my PLANNED trips", "my ACTIVE trip", etc.
        Index(
            "ix_trips_owner_id_status",
            "owner_id",
            "status",
        ),
        # Partial composite index: owner's live (non-deleted) trips ordered for
        # cursor-based pagination. PostgreSQL can use the partial index to skip
        # deleted rows without evaluating the WHERE clause row-by-row.
        Index(
            "ix_trips_owner_id_created_at_active",
            "owner_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        # Status must be one of the TripStatus enum values.
        CheckConstraint(
            "status IN ('draft', 'planned', 'active', 'completed', 'archived')",
            name="ck_trips_status",
        ),
        # Privacy must be one of the TripPrivacy enum values.
        CheckConstraint(
            "privacy IN ('private', 'link_only', 'public')",
            name="ck_trips_privacy",
        ),
        # A return date cannot be set without a departure date.
        CheckConstraint(
            "return_date IS NULL OR departure_date IS NOT NULL",
            name="ck_trips_return_requires_departure",
        ),
        # When both dates are present, the return must not precede departure.
        CheckConstraint(
            "return_date IS NULL OR return_date >= departure_date",
            name="ck_trips_dates_ordered",
        ),
    )

    # ---------------------------------------------------------------------- #
    # Representation                                                           #
    # ---------------------------------------------------------------------- #

    def __repr__(self) -> str:
        return (
            f"TripModel("
            f"id={self.id!r}, "
            f"owner_id={self.owner_id!r}, "
            f"title={self.title!r}, "
            f"status={self.status!r}"
            f")"
        )
