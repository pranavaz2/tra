"""Create locations table.

Revision ID: 20260702_0001
Revises:
Create Date: 2026-07-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260702_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Geometry(sa.types.UserDefinedType[object]):
    """PostGIS geometry type used by this migration."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        """Return the database column specification."""
        return "geometry(Point, 4326)"


def upgrade() -> None:
    """Apply the locations schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("location_type", sa.String(length=32), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("region", sa.String(length=255), nullable=True),
        sa.Column("locality", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=False),
        sa.Column("point", Geometry(), nullable=False),
        sa.Column("provider_place_id", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_locations_latitude_range"),
        sa.CheckConstraint(
            "longitude >= -180 AND longitude <= 180",
            name="ck_locations_longitude_range",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
    )
    op.create_index("ix_locations_slug", "locations", ["slug"], unique=True)
    op.create_index("ix_locations_country_code", "locations", ["country_code"])
    op.create_index("ix_locations_type", "locations", ["location_type"])
    op.create_index("ix_locations_deleted_at", "locations", ["deleted_at"])
    op.create_index("gix_locations_point", "locations", ["point"], postgresql_using="gist")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_locations_updated_at
        BEFORE UPDATE ON locations
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )


def downgrade() -> None:
    """Remove the locations schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_locations_updated_at ON locations")
    op.drop_index("gix_locations_point", table_name="locations", postgresql_using="gist")
    op.drop_index("ix_locations_deleted_at", table_name="locations")
    op.drop_index("ix_locations_type", table_name="locations")
    op.drop_index("ix_locations_country_code", table_name="locations")
    op.drop_index("ix_locations_slug", table_name="locations")
    op.drop_table("locations")
