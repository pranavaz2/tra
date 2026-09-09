"""Create notification preferences, sent notification logs, and device tokens tables.

Revision ID: 20260905_0009
Revises: 20260716_0008
Create Date: 2026-09-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260905_0009"
down_revision: str | None = "20260716_0008"
branch_labels: SaBranchLabels = None
depends_on: SaDependsOn = None

SaBranchLabels = str | Sequence[str] | None
SaDependsOn = str | Sequence[str] | None


def upgrade() -> None:
    # 1. notification_preferences
    op.create_table(
        "notification_preferences",
        sa.Column(
            "preference_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_notification_preferences_user_id_users", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("trip_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("itinerary_reminders", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("collaboration", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("budget_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("travel_warnings", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("weather_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours_start", sa.Time(), nullable=True),
        sa.Column("quiet_hours_end", sa.Time(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"])

    # 2. sent_notification_logs
    op.create_table(
        "sent_notification_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_sent_notification_logs_user_id_users", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("dedup_key", sa.String(length=255), unique=True, nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.String(length=1000), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_sent_notification_logs_user_id", "sent_notification_logs", ["user_id"])
    op.create_index("ix_sent_notification_logs_dedup_key", "sent_notification_logs", ["dedup_key"])
    op.create_index("ix_sent_notification_logs_trip_id", "sent_notification_logs", ["trip_id"])
    op.create_index("ix_sent_notifications_user_sent_at", "sent_notification_logs", ["user_id", "sent_at"])

    # 3. user_device_push_tokens
    op.create_table(
        "user_device_push_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_user_device_push_tokens_user_id_users", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(length=512), unique=True, nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False, server_default="expo"),
        sa.Column("device_name", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_user_device_push_tokens_user_id", "user_device_push_tokens", ["user_id"])
    op.create_index("ix_user_device_push_tokens_token", "user_device_push_tokens", ["token"])
    op.create_index("ix_user_device_push_tokens_user_id_platform", "user_device_push_tokens", ["user_id", "platform"])


def downgrade() -> None:
    op.drop_table("user_device_push_tokens")
    op.drop_table("sent_notification_logs")
    op.drop_table("notification_preferences")
