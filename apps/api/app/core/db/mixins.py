"""
Travix AI — ORM Column Mixins

Reusable column definitions applied to every SQLAlchemy model via mixin
inheritance. They implement the CLAUDE.md §10 schema requirements:

  - UUIDPrimaryKeyMixin   → `id` column, UUID v4, primary key
  - TimestampMixin        → `created_at` and `updated_at` with timezone
  - SoftDeleteMixin       → `deleted_at` with timezone, property `is_deleted`
  - OptimisticLockMixin   → `version` integer for optimistic concurrency control

Usage — compose mixins into an ORM model:

    from app.database import Base
    from app.core.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin

    class Trip(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
        __tablename__ = "trips"
        title: Mapped[str] = mapped_column(String(255), nullable=False)

Ordering convention: mixins LEFT of Base so their columns appear first in
Alembic-generated DDL. Apply in this order: UUID PK → timestamps → soft-delete
→ optimistic lock → Base.

Notes on updated_at:
  The `onupdate=func.now()` ensures the ORM adds `SET updated_at = now()` when
  executing an UPDATE through the ORM session. For bulk updates executed via
  `session.execute(update(Model).values(...))` or raw SQL, the column is NOT
  automatically updated — the migration for each table must include a PostgreSQL
  trigger:

      CREATE OR REPLACE FUNCTION set_updated_at()
      RETURNS TRIGGER AS $$
      BEGIN
          NEW.updated_at = NOW();
          RETURN NEW;
      END;
      $$ LANGUAGE plpgsql;

      CREATE TRIGGER trg_<table>_updated_at
      BEFORE UPDATE ON <table>
      FOR EACH ROW EXECUTE FUNCTION set_updated_at();

  See the migration template (migrations/script.py.mako) for the checklist
  reminder.

Notes on OptimisticLockMixin:
  Adding the column alone is not enough. The consuming model must activate
  SQLAlchemy's optimistic locking by including:

      __mapper_args__ = {"version_id_col": version}

  SQLAlchemy will then automatically:
    - Increment `version` on every UPDATE.
    - Raise `sqlalchemy.orm.exc.StaleDataError` if the stored version does not
      match the value in the session at update time (concurrent write detected).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """
    Adds an `id` column: UUID v4 primary key.

    The default is generated in Python (not the database) so the ID is
    available immediately after constructing the object, before it is
    flushed to the database. This is required for the domain event pattern
    where the aggregate ID must be known at construction time.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        sort_order=-100,  # appear first in the column list
    )


class TimestampMixin:
    """
    Adds `created_at` and `updated_at` columns with UTC timezone.

    Both columns default to the current database server time on INSERT.
    `updated_at` is refreshed on every ORM-triggered UPDATE via `onupdate`.
    See module docstring for the trigger requirement for non-ORM updates.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        sort_order=98,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        sort_order=99,
    )


class SoftDeleteMixin:
    """
    Adds a `deleted_at` nullable timestamp for soft-delete semantics.

    All queries in feature repositories MUST filter `WHERE deleted_at IS NULL`
    to exclude deleted records. Use the query helper:

        from app.core.db.query import exclude_deleted
        stmt = exclude_deleted(select(TripModel), TripModel)

    The `deleted_at` column is indexed to make this filter efficient.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
        sort_order=100,
    )

    @property
    def is_deleted(self) -> bool:
        """Return True if this record has been soft-deleted."""
        return self.deleted_at is not None


class OptimisticLockMixin:
    """
    Adds a `version` integer column for optimistic concurrency control.

    See module docstring for the required `__mapper_args__` configuration
    needed to activate SQLAlchemy's automatic version checking.
    """

    version: Mapped[int] = mapped_column(
        Integer,
        server_default=text("1"),
        nullable=False,
        sort_order=101,
    )
