"""Create trip media collections and media items tables.

Revision ID: 20260716_0007
Revises: 20260716_0006
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0007"
down_revision: str | None = "20260716_0006"
branch_labels: SaBranchLabels = None
depends_on: SaDependsOn = None

SaBranchLabels = str | Sequence[str] | None
SaDependsOn = str | Sequence[str] | None


def upgrade() -> None:
    """Apply media context schema."""

    # 1. Create trip_media_collections table
    op.create_table(
        "trip_media_collections",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "trip_id",
            sa.UUID(),
            sa.ForeignKey(
                "trips.id",
                name="fk_trip_media_collections_trip_id_trips",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="The trip this media collection belongs to.",
        ),
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey(
                "users.id",
                name="fk_trip_media_collections_owner_id_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="The user who owns this media collection.",
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
            comment="Optimistic lock version counter.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trip_media_collections"),
        sa.UniqueConstraint("trip_id", name="uq_trip_media_collections_trip_id"),
    )

    # Indexes on trip_media_collections
    op.create_index(
        "ix_trip_media_collections_trip_id",
        "trip_media_collections",
        ["trip_id"],
    )
    op.create_index(
        "ix_trip_media_collections_owner_id",
        "trip_media_collections",
        ["owner_id"],
    )
    op.create_index(
        "ix_trip_media_collections_deleted_at",
        "trip_media_collections",
        ["deleted_at"],
    )
    op.create_index(
        "ix_trip_media_collections_owner_id_active",
        "trip_media_collections",
        ["owner_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Trigger to set updated_at
    op.execute("""
        CREATE TRIGGER trg_trip_media_collections_updated_at
        BEFORE UPDATE ON trip_media_collections
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # 2. Create media_items table
    op.create_table(
        "media_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "collection_id",
            sa.UUID(),
            sa.ForeignKey(
                "trip_media_collections.id",
                name="fk_media_items_collection_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "url",
            sa.String(2048),
            nullable=False,
            comment="The HTTPS URL where the file is stored.",
        ),
        sa.Column(
            "media_type",
            sa.String(32),
            nullable=False,
            comment="Media category: photo, video, note, voice_memo, receipt.",
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            comment="Current status of the upload/item: uploading, available, failed, deleted.",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Extracted metadata fields (file name, dimensions, file size, duration, etc.).",
        ),
        sa.Column(
            "caption",
            sa.Text(),
            nullable=True,
            comment="Optional descriptive caption for the media item.",
        ),
        sa.Column(
            "uploaded_by",
            sa.UUID(),
            sa.ForeignKey(
                "users.id",
                name="fk_media_items_uploaded_by_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            sa.UUID(),
            sa.ForeignKey(
                "itinerary_items.id",
                name="fk_media_items_activity_id_itinerary_items",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "expense_id",
            sa.UUID(),
            sa.ForeignKey(
                "expenses.id",
                name="fk_media_items_expense_id_expenses",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_media_items"),
    )

    op.create_index(
        "ix_media_items_collection_id",
        "media_items",
        ["collection_id"],
    )
    op.create_index(
        "ix_media_items_uploaded_by",
        "media_items",
        ["uploaded_by"],
    )
    op.create_index(
        "ix_media_items_activity_id",
        "media_items",
        ["activity_id"],
    )
    op.create_index(
        "ix_media_items_expense_id",
        "media_items",
        ["expense_id"],
    )
    op.create_index(
        "ix_media_items_collection_id_created_at",
        "media_items",
        ["collection_id", "created_at"],
    )

    # Trigger to set updated_at
    op.execute("""
        CREATE TRIGGER trg_media_items_updated_at
        BEFORE UPDATE ON media_items
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    """Reverse media context schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_media_items_updated_at ON media_items;")
    op.execute("DROP TRIGGER IF EXISTS trg_trip_media_collections_updated_at ON trip_media_collections;")

    op.drop_table("media_items")
    op.drop_table("trip_media_collections")
