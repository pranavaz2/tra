"""Create user preferences table for recommendations.

Revision ID: 20260716_0008
Revises: 20260716_0007
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0008"
down_revision: str | None = "20260716_0007"
branch_labels: SaBranchLabels = None
depends_on: SaDependsOn = None

SaBranchLabels = str | Sequence[str] | None
SaDependsOn = str | Sequence[str] | None


def upgrade() -> None:
    """Apply recommendations context schema."""

    # 1. Create user_preferences table
    op.create_table(
        "user_preferences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey(
                "users.id",
                name="fk_user_preferences_user_id_users",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="The user who owns these preferences.",
        ),
        sa.Column(
            "interests",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="JSON array of interest tags.",
        ),
        sa.Column(
            "dietary_preferences",
            sa.JSON(),
            nullable=False,
            server_default="[]",
            comment="JSON array of dietary preference tags.",
        ),
        sa.Column("travel_style", sa.String(length=50), nullable=False, server_default="culture"),
        sa.Column("travel_pace", sa.String(length=50), nullable=False, server_default="medium"),
        sa.Column("budget_tier", sa.String(length=50), nullable=False, server_default="mid_range"),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Optimistic locking version.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record creation timestamp.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
            comment="Record update timestamp.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_preferences"),
        sa.UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )

    # 2. Add index for user_id lookup
    op.create_index(
        "ix_user_preferences_user_id",
        "user_preferences",
        ["user_id"],
    )

    # 3. Add trigger to update updated_at timestamp automatically
    op.execute("""
        CREATE TRIGGER trg_user_preferences_updated_at
        BEFORE UPDATE ON user_preferences
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    """Reverse recommendations context schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_user_preferences_updated_at ON user_preferences;")
    op.drop_index("ix_user_preferences_user_id", table_name="user_preferences")
    op.drop_table("user_preferences")
