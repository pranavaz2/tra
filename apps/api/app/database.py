"""
Travix AI — Database Infrastructure

Provides:
  - SQLAlchemy async engine (lazy-initialized, connection-pooled)
  - Async session factory
  - DeclarativeBase with enforced naming conventions
  - FastAPI session dependency
  - Startup/shutdown lifecycle helpers
  - Database health check for /ready endpoint

All ORM models must inherit from Base defined here.

Naming convention for constraints (auto-applied by SQLAlchemy):
  ix_  → indexes
  uq_  → unique constraints
  ck_  → check constraints
  fk_  → foreign keys
  pk_  → primary keys
  gix_ → PostGIS GiST indexes (managed manually in migrations)
"""

from __future__ import annotations

import logging
import time
from typing import AsyncGenerator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.

    All models must inherit from this class. The naming convention ensures
    consistent constraint names across databases and Alembic migrations.

    Standard model template (combine relevant mixins):

        from app.database import Base
        from app.core.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin

        class Trip(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
            __tablename__ = "trips"
            title: Mapped[str] = mapped_column(String(255), nullable=False)

    Required columns per CLAUDE.md §10 (enforced by mixins):
      - id          UUID primary key (UUIDPrimaryKeyMixin)
      - created_at  timestamp with timezone (TimestampMixin)
      - updated_at  timestamp with timezone, auto-updates (TimestampMixin)
      - deleted_at  nullable timestamp for soft-delete (SoftDeleteMixin)
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# ---------------------------------------------------------------------------
# Lazy engine and session factory
# ---------------------------------------------------------------------------
# Engine is created on first use to allow test environment variables to be
# set before any app module is imported.

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _build_engine() -> AsyncEngine:
    """Create the async SQLAlchemy engine from current settings."""
    from app.config import get_settings
    from app.core.db.events import register_query_hooks

    s = get_settings()
    logger.debug(
        "Initialising database engine",
        extra={
            "pool_size": s.db_pool_size,
            "max_overflow": s.db_max_overflow,
            "pool_timeout": s.db_pool_timeout,
            "pool_recycle": s.db_pool_recycle,
        },
    )

    engine = create_async_engine(
        s.database_url.get_secret_value(),
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_timeout=s.db_pool_timeout,
        # Recycle connections after this many seconds to prevent PostgreSQL
        # from closing idle connections (default wait_timeout is 8h on most hosts).
        pool_recycle=s.db_pool_recycle,
        # Issue a lightweight SELECT 1 before using a connection from the pool.
        # Detects stale connections without requiring explicit error handling.
        pool_pre_ping=s.db_pool_pre_ping,
        # Echo SQL statements only in local dev to avoid leaking query structure in logs.
        echo=s.is_local,
    )

    # Register query timing and slow-query detection hooks.
    register_query_hooks(engine, threshold_ms=s.db_slow_query_threshold_ms)

    return engine


def get_engine() -> AsyncEngine:
    """Return the singleton async engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the singleton session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            # Do not expire ORM objects after commit — avoids unintended lazy
            # loads when accessing attributes after the transaction is closed.
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional database session.

    Commits on success, rolls back on any exception. The session is closed
    when the request context exits.

    For multi-aggregate operations that need explicit transaction control,
    use ``SQLAlchemyUnitOfWork`` instead of this dependency.

    Usage:
        from app.dependencies import DatabaseSession

        @router.get("/trips/{id}")
        async def get_trip(db: DatabaseSession) -> TripResponse:
            ...
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def close_db() -> None:
    """
    Dispose the connection pool gracefully.

    Waits for all checked-out connections to be returned before closing.
    Registered automatically in the app.main lifespan context manager.
    """
    global _engine, _session_factory
    if _engine is not None:
        logger.info("Closing database connection pool")
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.debug("Database engine disposed")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def check_database_health() -> dict[str, object]:
    """
    Execute a lightweight query to verify database connectivity and latency.

    Returns a dict compatible with the HealthResponse.checks schema.
    Never raises — failures are captured and returned as unhealthy status.
    Used by the /ready endpoint.
    """
    start = time.monotonic()
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error(
            "Database health check failed",
            extra={"error": type(exc).__name__, "latency_ms": latency_ms},
        )
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": type(exc).__name__,
        }
