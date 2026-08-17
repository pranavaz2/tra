"""Create itineraries, days, and items tables.

Revision ID: 20260710_0003
Revises: 20260710_0002
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260710_0003"
down_revision: str | None = "20260710_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the itineraries schema."""
    # 1. Create itineraries table
    op.create_table(
        "itineraries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "trip_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Trip that owns this itinerary.",
        ),
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
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic concurrency version.",
        ),
        sa.ForeignKeyConstraint(
            ["trip_id"],
            ["trips.id"],
            name="fk_itineraries_trip_id_trips",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_itineraries"),
    )

    # 2. Create itinerary_days table
    op.create_table(
        "itinerary_days",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "itinerary_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Itinerary that owns this day.",
        ),
        sa.Column(
            "day_number",
            sa.Integer(),
            nullable=False,
            comment="Sequential day index (1-based).",
        ),
        sa.Column(
            "title",
            sa.String(length=100),
            nullable=True,
            comment="Optional descriptive name for this day.",
        ),
        sa.Column(
            "date",
            sa.Date(),
            nullable=True,
            comment="Specific calendar date for this day.",
        ),
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
        sa.ForeignKeyConstraint(
            ["itinerary_id"],
            ["itineraries.id"],
            name="fk_itinerary_days_itinerary_id_itineraries",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_itinerary_days"),
        sa.UniqueConstraint(
            "itinerary_id",
            "day_number",
            name="uq_itinerary_days_itinerary_day_number",
        ),
        sa.CheckConstraint(
            "day_number >= 1",
            name="ck_itinerary_days_day_number",
        ),
    )

    # 3. Create itinerary_items table
    op.create_table(
        "itinerary_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "day_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Day that contains this item.",
        ),
        sa.Column(
            "title",
            sa.String(length=100),
            nullable=False,
            comment="Brief description of this activity.",
        ),
        sa.Column(
            "item_type",
            sa.String(length=32),
            nullable=False,
            comment="Category: activity | transport | lodging | restaurant.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Detailed notes, links, or instructions.",
        ),
        sa.Column(
            "start_time",
            sa.Time(),
            nullable=True,
            comment="Scheduled start time of this item.",
        ),
        sa.Column(
            "end_time",
            sa.Time(),
            nullable=True,
            comment="Scheduled end time of this item.",
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Optional location ID reference.",
        ),
        sa.Column(
            "cost",
            sa.Numeric(precision=10, scale=2),
            nullable=True,
            comment="Estimated cost.",
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=True,
            comment="Three-letter currency code.",
        ),
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
        sa.ForeignKeyConstraint(
            ["day_id"],
            ["itinerary_days.id"],
            name="fk_itinerary_items_day_id_itinerary_days",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["location_id"],
            ["locations.id"],
            name="fk_itinerary_items_location_id_locations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_itinerary_items"),
        sa.CheckConstraint(
            "item_type IN ('activity', 'transport', 'lodging', 'restaurant')",
            name="ck_itinerary_items_item_type",
        ),
    )

    # --- Indexes ---
    op.create_index(
        "ix_itineraries_trip_id",
        "itineraries",
        ["trip_id"],
        unique=True,
    )
    op.create_index(
        "ix_itineraries_deleted_at",
        "itineraries",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        "ix_itinerary_days_itinerary_id",
        "itinerary_days",
        ["itinerary_id"],
        unique=False,
    )
    op.create_index(
        "ix_itinerary_items_day_id",
        "itinerary_items",
        ["day_id"],
        unique=False,
    )
    op.create_index(
        "ix_itinerary_items_location_id",
        "itinerary_items",
        ["location_id"],
        unique=False,
    )

    # --- Triggers ---
    op.execute(
        """
        CREATE TRIGGER trg_itineraries_updated_at
        BEFORE UPDATE ON itineraries
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_itinerary_days_updated_at
        BEFORE UPDATE ON itinerary_days
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_itinerary_items_updated_at
        BEFORE UPDATE ON itinerary_items
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    """Remove the itineraries schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_itinerary_items_updated_at ON itinerary_items")
    op.execute("DROP TRIGGER IF EXISTS trg_itinerary_days_updated_at ON itinerary_days")
    op.execute("DROP TRIGGER IF EXISTS trg_itineraries_updated_at ON itineraries")

    op.drop_index("ix_itinerary_items_location_id", table_name="itinerary_items")
    op.drop_index("ix_itinerary_items_day_id", table_name="itinerary_items")
    op.drop_index("ix_itinerary_days_itinerary_id", table_name="itinerary_days")
    op.drop_index("ix_itineraries_deleted_at", table_name="itineraries")
    op.drop_index("ix_itineraries_trip_id", table_name="itineraries")

    op.drop_table("itinerary_items")
    op.drop_table("itinerary_days")
    op.drop_table("itineraries")
