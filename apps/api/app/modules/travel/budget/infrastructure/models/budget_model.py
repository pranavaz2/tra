"""TripBudget ORM models."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.core.db.mixins import (
    OptimisticLockMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)
from app.database import Base


class TripBudgetModel(
    UUIDPrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
    OptimisticLockMixin,
    Base,
):
    """ORM model for trip_budgets table."""

    __tablename__ = "trip_budgets"

    trip_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        sort_order=1,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        sort_order=2,
    )

    limit_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        sort_order=3,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        sort_order=4,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'active'"),
        sort_order=5,
    )

    categories: Mapped[list[BudgetCategoryModel]] = relationship(
        "BudgetCategoryModel",
        back_populates="budget",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="BudgetCategoryModel.name",
    )

    expenses: Mapped[list[ExpenseModel]] = relationship(
        "ExpenseModel",
        back_populates="budget",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ExpenseModel.expense_date.desc(), ExpenseModel.created_at.desc()",
    )

    @declared_attr.directive  # type: ignore[override]
    def __mapper_args__(self) -> dict[str, Any]:
        return {"version_id_col": self.__table__.c.version}

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'closed')",
            name="ck_trip_budgets_status",
        ),
        CheckConstraint(
            "limit_amount > 0",
            name="ck_trip_budgets_limit_amount",
        ),
        Index(
            "ix_trip_budgets_owner_id_created_at_active",
            "owner_id",
            "created_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )


class BudgetCategoryModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for budget_categories table."""

    __tablename__ = "budget_categories"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trip_budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        sort_order=2,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        sort_order=3,
    )

    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        sort_order=4,
    )

    budget: Mapped[TripBudgetModel] = relationship(
        "TripBudgetModel",
        back_populates="categories",
    )

    __table_args__ = (
        UniqueConstraint(
            "budget_id",
            "name",
            name="uq_budget_categories_budget_id_name",
        ),
    )


class ExpenseModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """ORM model for expenses table."""

    __tablename__ = "expenses"

    budget_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("trip_budgets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        sort_order=1,
    )

    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        sort_order=2,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        sort_order=3,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        sort_order=4,
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("budget_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        sort_order=5,
    )

    expense_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        sort_order=6,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        sort_order=7,
    )

    expense_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        sort_order=8,
    )

    budget: Mapped[TripBudgetModel] = relationship(
        "TripBudgetModel",
        back_populates="expenses",
    )

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_expenses_amount",
        ),
        CheckConstraint(
            "expense_type IN ('activity', 'transport', 'lodging', 'restaurant', 'other')",
            name="ck_expenses_expense_type",
        ),
        Index(
            "ix_expenses_budget_id_expense_date",
            "budget_id",
            "expense_date",
        ),
    )
