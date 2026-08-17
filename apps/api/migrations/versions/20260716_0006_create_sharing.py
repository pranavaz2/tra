"""Create trip collaborations, members, and invitations tables.

Revision ID: 20260716_0006
Revises: 20260714_0005
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0006"
down_revision: str | None = "20260714_0005"
branch_labels: SaBranchLabels = None
depends_on: SaDependsOn = None

SaBranchLabels = str | Sequence[str] | None
SaDependsOn = str | Sequence[str] | None


def upgrade() -> None:
    """Apply sharing context schema."""

    # 1. Create trip_collaborations table
    op.create_table(
        "trip_collaborations",
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
                name="fk_trip_collaborations_trip_id_trips",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="The trip this collaboration belongs to.",
        ),
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey(
                "users.id",
                name="fk_trip_collaborations_owner_id_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="The user who owns this trip.",
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether public (read-only) access is enabled.",
        ),
        sa.Column(
            "share_token",
            sa.String(128),
            nullable=True,
            comment="Opaque public share token (64-char hex). NULL when not public.",
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
        sa.PrimaryKeyConstraint("id", name="pk_trip_collaborations"),
        sa.UniqueConstraint("trip_id", name="uq_trip_collaborations_trip_id"),
        sa.UniqueConstraint("share_token", name="uq_trip_collaborations_share_token"),
    )

    # Indexes on trip_collaborations
    op.create_index(
        "ix_trip_collaborations_trip_id",
        "trip_collaborations",
        ["trip_id"],
    )
    op.create_index(
        "ix_trip_collaborations_owner_id",
        "trip_collaborations",
        ["owner_id"],
    )
    op.create_index(
        "ix_trip_collaborations_share_token",
        "trip_collaborations",
        ["share_token"],
        unique=True,
    )
    op.create_index(
        "ix_trip_collaborations_deleted_at",
        "trip_collaborations",
        ["deleted_at"],
    )
    op.create_index(
        "ix_trip_collaborations_owner_id_active",
        "trip_collaborations",
        ["owner_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # updated_at trigger for trip_collaborations
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_trip_collaborations_updated_at
        BEFORE UPDATE ON trip_collaborations
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # 2. Create trip_members table
    op.create_table(
        "trip_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "collaboration_id",
            sa.UUID(),
            sa.ForeignKey(
                "trip_collaborations.id",
                name="fk_trip_members_collaboration_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            sa.ForeignKey(
                "users.id",
                name="fk_trip_members_user_id_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            comment="Member role: owner, editor, or viewer.",
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id", name="pk_trip_members"),
        sa.UniqueConstraint(
            "collaboration_id",
            "user_id",
            name="uq_trip_members_collaboration_user",
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_trip_members_role",
        ),
    )

    op.create_index(
        "ix_trip_members_collaboration_id",
        "trip_members",
        ["collaboration_id"],
    )
    op.create_index(
        "ix_trip_members_user_id",
        "trip_members",
        ["user_id"],
    )

    op.execute("""
        CREATE TRIGGER trg_trip_members_updated_at
        BEFORE UPDATE ON trip_members
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)

    # 3. Create trip_invitations table
    op.create_table(
        "trip_invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "collaboration_id",
            sa.UUID(),
            sa.ForeignKey(
                "trip_collaborations.id",
                name="fk_trip_invitations_collaboration_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "invitee_email",
            sa.String(255),
            nullable=False,
            comment="Email address of the invited user.",
        ),
        sa.Column(
            "role",
            sa.String(20),
            nullable=False,
            comment="Role to grant on acceptance.",
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            comment="Invitation lifecycle status.",
        ),
        sa.Column(
            "token",
            sa.String(128),
            nullable=False,
            comment="Opaque invitation token for the accept-by-link flow.",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id", name="pk_trip_invitations"),
        sa.UniqueConstraint("token", name="uq_trip_invitations_token"),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer')",
            name="ck_trip_invitations_role",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'declined', 'expired', 'revoked')",
            name="ck_trip_invitations_status",
        ),
    )

    op.create_index(
        "ix_trip_invitations_collaboration_id",
        "trip_invitations",
        ["collaboration_id"],
    )
    op.create_index(
        "ix_trip_invitations_token",
        "trip_invitations",
        ["token"],
        unique=True,
    )
    op.create_index(
        "ix_trip_invitations_deleted_at",
        "trip_invitations",
        ["deleted_at"],
    )
    op.create_index(
        "ix_trip_invitations_collaboration_email_pending",
        "trip_invitations",
        ["collaboration_id", "invitee_email"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.execute("""
        CREATE TRIGGER trg_trip_invitations_updated_at
        BEFORE UPDATE ON trip_invitations
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    """)


def downgrade() -> None:
    """Reverse sharing context schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_trip_invitations_updated_at ON trip_invitations;")
    op.execute("DROP TRIGGER IF EXISTS trg_trip_members_updated_at ON trip_members;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_trip_collaborations_updated_at ON trip_collaborations;"
    )

    op.drop_table("trip_invitations")
    op.drop_table("trip_members")
    op.drop_table("trip_collaborations")
