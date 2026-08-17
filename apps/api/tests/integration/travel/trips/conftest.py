"""
Local fixtures for Trips repository integration tests.

Overrides the session-scoped db_engine from the global conftest.py to:
  1. Create a minimal `users` stub table first (satisfies TripModel's FK).
  2. Import and create TripModel's table via SQLAlchemy create_all.

This is isolated to the trips integration tests — global integration tests
(locations, etc.) continue to use the original db_engine fixture unmodified.

The global db_session and uow_factory fixtures resolve fixtures by name,
so they automatically pick up the local db_engine defined here.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

# Set env vars before any app import (mirrors the global conftest.py).
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("APP_DEBUG", "false")
os.environ.setdefault("APP_VERSION", "0.0.0-test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://travix:travix_password@localhost:5432/travix_test",
)
os.environ.setdefault(
    "DATABASE_SYNC_URL",
    "postgresql+psycopg2://travix:travix_password@localhost:5432/travix_test",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production-use-only")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("MAPS_PROVIDER", "mock")
os.environ.setdefault("EMAIL_PROVIDER", "mock")
os.environ.setdefault("STORAGE_PROVIDER", "mock")
os.environ.setdefault("NOTIFICATION_PROVIDER", "mock")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "text")

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Session-scoped engine for the trips integration tests.

    Creates the stub `users` table (for FK resolution) then creates all
    tables defined in the shared SQLAlchemy Base (including TripModel).

    The global conftest.py db_engine is shadowed by this fixture for all
    tests in tests/integration/travel/trips/.
    """
    from app.config import get_settings
    from app.database import Base

    # Must import TripModel so its metadata is registered on Base before create_all.
    from app.modules.travel.trips.infrastructure.models.trip_model import TripModel  # noqa: F401

    settings = get_settings()
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        # Create stub users table first so TripModel's FK is satisfied.
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        # Create all ORM-registered tables (includes trips).
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # Drop the stub users table after ORM tables are gone.
        await conn.execute(text("DROP TABLE IF EXISTS users"))

    await engine.dispose()


@pytest_asyncio.fixture
async def trip_owner_id(db_session: AsyncSession) -> uuid.UUID:
    """
    Insert a stub user row and return its UUID.

    The row is inserted within the per-test transaction that db_session wraps,
    so it is automatically rolled back at the end of the test — no cleanup needed.
    """
    uid = uuid.uuid4()
    await db_session.execute(
        text("INSERT INTO users (id, email) VALUES (:id, :email)"),
        {"id": uid, "email": f"test-{uid}@example.com"},
    )
    return uid
