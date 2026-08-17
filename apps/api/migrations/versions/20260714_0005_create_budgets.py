"""Create trip budgets, categories, and expenses tables.

Revision ID: 20260714_0005
Revises: 20260714_0004
Create Date: 2026-07-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0005"
down_revision: str | None = "20260714_0004"
branch_labels: SaBranchLabels = None
depends_on: SaDependsOn = None

SaBranchLabels = str | Sequence[str] | None
SaDependsOn = str | Sequence[str] | None


def upgrade() -> None:
    """Apply budget context schema."""
    # 1. Create trip_budgets table
    op.create_table(
        "trip_budgets",
         sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            "owner_id",
            sa.UUID(),
            sa.ForeignKey(
                "users.id",
                name="fk_trip_budgets_owner_id_users",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="Owner of the budget context.",
        ),
        sa.Column(
            trip_id_col := "trip_id",
            sa.UUID(),
            sa.ForeignKey(
                "trips.id",
                name="fk_trip_budgets_trip_id_trips",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="Trip associated with this budget.",
        ),
        sa.Column(
            "limit_amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="Total budget limit amount.",
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            comment="3-letter currency code.",
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
            comment="Budget lifecycle status.",
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
            server_default=sa.text("1"),
            nullable=False,
            comment="Optimistic locking version ID.",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_trip_budgets"),
        sa.CheckConstraint(
            "status IN ('active', 'closed')",
            name="ck_trip_budgets_status",
        ),
        sa.CheckConstraint(
            "limit_amount > 0",
            name="ck_trip_budgets_limit_amount",
        ),
    )

    op.create_index(
        "ix_trip_budgets_owner_id_created_at_active",
        "trip_budgets",
        ["owner_id", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_trip_budgets_trip_id",
        "trip_budgets",
        [trip_id_col],
        unique=True,
    )
    op.create_index(
        "ix_trip_budgets_deleted_at",
        "trip_budgets",
        ["deleted_at"],
        unique=False,
    )

    op.execute(
        """
        CREATE TRIGGER trg_trip_budgets_updated_at
        BEFORE UPDATE ON trip_budgets
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    # 2. Create budget_categories table
    op.create_table(
        "budget_categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            budget_id_col := "budget_id",
            sa.UUID(),
            sa.ForeignKey(
                "trip_budgets.id",
                name="fk_budget_categories_budget_id_trip_budgets",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="Budget this category belongs to.",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Display name of the category.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional category description.",
        ),
        sa.Column(
            "icon",
            sa.String(length=50),
            nullable=True,
            comment="Optional category icon slug.",
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
        sa.PrimaryKeyConstraint("id", name="pk_budget_categories"),
        sa.UniqueConstraint(budget_id_col, "name", name="uq_budget_categories_budget_id_name"),
    )

    op.create_index(
        "ix_budget_categories_budget_id",
        "budget_categories",
        [budget_id_col],
        unique=False,
    )

    op.execute(
        """
        CREATE TRIGGER trg_budget_categories_updated_at
        BEFORE UPDATE ON budget_categories
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )

    # 3. Create expenses table
    op.create_table(
        "expenses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID v4 primary key.",
        ),
        sa.Column(
            budget_id_col,
            sa.UUID(),
            sa.ForeignKey(
                "trip_budgets.id",
                name="fk_expenses_budget_id_trip_budgets",
                ondelete="CASCADE",
            ),
            nullable=False,
            comment="Budget this expense is charged to.",
        ),
        sa.Column(
            "title",
            sa.String(length=100),
            nullable=False,
            comment="Title of the expense item.",
        ),
        sa.Column(
            "amount",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            comment="Spend amount value.",
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            comment="3-letter currency code.",
        ),
        sa.Column(
            category_id_col := "category_id",
            sa.UUID(),
            sa.ForeignKey(
                "budget_categories.id",
                name="fk_expenses_category_id_budget_categories",
                ondelete="RESTRICT",
            ),
            nullable=False,
            comment="Associated category.",
        ),
        sa.Column(
            "expense_type",
            sa.String(length=32),
            nullable=False,
            comment="Category type tag.",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Optional details description.",
        ),
        sa.Column(
            "expense_date",
            sa.Date(),
            nullable=False,
            comment="Date of spend.",
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
        sa.PrimaryKeyConstraint("id", name="pk_expenses"),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_expenses_amount",
        ),
        sa.CheckConstraint(
            "expense_type IN ('activity', 'transport', 'lodging', 'restaurant', 'other')",
            name="ck_expenses_expense_type",
        ),
    )

    op.create_index(
        "ix_expenses_budget_id_expense_date",
        "expenses",
        [budget_id_col, "expense_date"],
        unique=False,
    )
    op.create_index(
        "ix_expenses_category_id",
        "expenses",
        [category_id_col],
        unique=False,
    )

    op.execute(
        """
        CREATE TRIGGER trg_expenses_updated_at
        BEFORE UPDATE ON expenses
        FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """
    )


def downgrade() -> None:
    """Remove the budget context schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_expenses_updated_at ON expenses")
    op.execute("DROP TRIGGER IF EXISTS trg_budget_categories_updated_at ON budget_categories")
    op.execute("DROP TRIGGER IF EXISTS trg_trip_budgets_updated_at ON trip_budgets")

    op.drop_index("ix_expenses_category_id", table_name="expenses")
    op.drop_index("ix_expenses_budget_id_expense_date", table_name="expenses")
    op.drop_table("expenses")

    op.drop_index("ix_budget_categories_budget_id", table_name="budget_categories")
    op.drop_table("budget_categories")

    op.drop_index("ix_trip_budgets_deleted_at", table_name="trip_budgets")
    op.drop_index("ix_trip_budgets_trip_id", table_name="trip_budgets")
    op.drop_index("ix_trip_budgets_owner_id_created_at_active", table_name="trip_budgets")
    op.drop_table("trip_budgets")
