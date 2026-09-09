"""Widen estimated_total_cost column from VARCHAR(50) to VARCHAR(500).

AI-generated cost strings regularly exceed the 50-character limit,
causing StringDataRightTruncationError on INSERT/UPDATE.

Revision ID: 20260909_0011
Revises: 20260905_0010
Create Date: 2026-09-09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0011"
down_revision = "20260905_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "trip_proposals",
        "estimated_total_cost",
        existing_type=sa.String(50),
        type_=sa.String(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "trip_proposals",
        "estimated_total_cost",
        existing_type=sa.String(500),
        type_=sa.String(50),
        existing_nullable=True,
    )
