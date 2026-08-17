"""Create trips table.

This migration creates:
  - trips table with all business columns, constraints, and indexes.
  - users stub table check: the trips table has a FK to users.id (ON DELETE RESTRICT).
    The users table must already exist before this migration runs.
    In production, the users/credentials tables are created by a prior migration in the
    identity module. This migration depends on that chain.
  - updated_at trigger so bulk SQL updates also refresh the timestamp.
  - Composite indexes optimised for the two primary query paths:
      ix_trips_owner_id_status         — list trips filtered by status
      ix_trips_owner_id_created_at_active — cursor pagination (partial, deleted_at IS NULL)

Revision ID: 20260710_0002
Revises: 20260702_0001
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0002"
down_revision: str | None = "20260702_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the trips schema."""
    op.create_table(
        "trips",
        # Primary key
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key, generated in Python before INSERT.",
        ),
        # Business columns
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User who created and owns this trip.",
        ),
        sa.Column(
            "title",
            sa.String(length=100),
            nullable=False,
            comment="Stripped trip name. 1–100 characters.",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'draft'"),
            comment="Trip lifecycle status. See TripStatus domain enum for valid values.",
        ),
        sa.Column(
            "privacy",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'private'"),
            comment="Visibility setting. See TripPrivacy domain enum for valid values.",
        ),
        sa.Column(
            "departure_date",
            sa.Date(),
            nullable=True,
            comment="First day of the trip. NULL when no dates are scheduled.",
        ),
        sa.Column(
            "return_date",
            sa.Date(),
            nullable=True,
            comment="Last day of the trip. NULL for open-ended trips or unscheduled trips.",
        ),
        sa.Column(
            "is_date_flexible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="True when the user has not committed to exact travel dates.",
        ),
        # Audit / lifecycle columns (from mixins)
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Optimistic concurrency version
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency counter. Incremented by SQLAlchemy on every UPDATE.",
        ),
        # Constraints
        sa.CheckConstraint(
            "status IN ('draft', 'planned', 'active', 'completed', 'archived')",
            name="ck_trips_status",
        ),
        sa.CheckConstraint(
            "privacy IN ('private', 'link_only', 'public')",
            name="ck_trips_privacy",
        ),
        sa.CheckConstraint(
            "return_date IS NULL OR departure_date IS NOT NULL",
            name="ck_trips_return_requires_departure",
        ),
        sa.CheckConstraint(
            "return_date IS NULL OR return_date >= departure_date",
            name="ck_trips_dates_ordered",
        ),
        # Foreign key: owner_id → users.id
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_trips_owner_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trips"),
    )

    # --- Indexes ---

    # Single-column index on owner_id (fast lookup of all trips by owner)
    op.create_index(
        "ix_trips_owner_id",
        "trips",
        ["owner_id"],
        unique=False,
    )

    # Composite index: owner_id + status — covers "list my planned trips" query path
    op.create_index(
        "ix_trips_owner_id_status",
        "trips",
        ["owner_id", "status"],
        unique=False,
    )

    # Partial composite index: owner's live (non-deleted) trips ordered for cursor pagination.
    # PostgreSQL partial indexes skip deleted rows without a full scan.
    op.create_index(
        "ix_trips_owner_id_created_at_active",
        "trips",
        ["owner_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Index on deleted_at for soft-delete filtering efficiency
    op.create_index(
        "ix_trips_deleted_at",
        "trips",
        ["deleted_at"],
        unique=False,
    )

    # --- updated_at trigger ---
    # set_updated_at() function is already created by the locations migration (20260702_0001).
    # We reuse it here — no need to re-create the function.
    op.execute(
        """
        CREATE TRIGGER trg_trips_updated_at
        BEFORE UPDATE ON trips
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    """Remove the trips schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_trips_updated_at ON trips")
    op.drop_index("ix_trips_deleted_at", table_name="trips")
    op.drop_index("ix_trips_owner_id_created_at_active", table_name="trips")
    op.drop_index("ix_trips_owner_id_status", table_name="trips")
    op.drop_index("ix_trips_owner_id", table_name="trips")
    op.drop_table("trips")
