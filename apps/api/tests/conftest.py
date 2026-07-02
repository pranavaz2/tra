"""
Travix AI — Test Configuration

IMPORTANT: Environment variables MUST be set before any app module is imported.
The block below runs at collection time, before pytest imports test files.
This ensures get_settings() reads test values, not real .env values.

Test architecture:
  Unit tests      → No external dependencies. Use MockAIProvider, MockMapsProvider.
                    No database or Redis required. Run with: pytest tests/unit/
  Integration tests → Require PostgreSQL + Redis running (via Docker Compose).
                    Use real database with a dedicated test schema.
                    Run with: pytest tests/integration/

Fixture scopes:
  session → created once per pytest run (engine, app)
  function → created fresh per test (db_session, client)

Transaction isolation strategy:
  Each test function gets an ``AsyncSession`` bound to an outer transaction
  that is ROLLED BACK at the end of the test. This means:
    - Tests start with a clean slate (leftover data from previous tests is gone).
    - No table truncation or database teardown is needed between tests.
    - Tests run significantly faster than recreating the schema each time.

  Important: Do NOT call ``session.commit()`` inside test functions directly.
  Use the UoW fixtures (``uow_factory``) when testing transaction boundaries.

All AI, Maps, Storage, Email, and Notification providers are set to "mock"
so no real API credentials are needed to run the test suite.
"""

from __future__ import annotations

import os
from collections.abc import AsyncGenerator

# ── Test environment variables ───────────────────────────────────────────────
# Set BEFORE any app imports so get_settings() returns these values.
# Use os.environ.setdefault so explicitly set CI variables take precedence.

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

# These values are not real secrets — test-only signing keys
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production-use-only")

# All external service providers set to mock — no live API calls in tests
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault("MAPS_PROVIDER", "mock")
os.environ.setdefault("EMAIL_PROVIDER", "mock")
os.environ.setdefault("STORAGE_PROVIDER", "mock")
os.environ.setdefault("NOTIFICATION_PROVIDER", "mock")

os.environ.setdefault("LOG_LEVEL", "WARNING")  # Suppress noise during tests
os.environ.setdefault("LOG_FORMAT", "text")

# ── Imports (after env vars are set) ─────────────────────────────────────────

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


# ── Session-scoped fixtures ───────────────────────────────────────────────────


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Use asyncio as the anyio backend for all async tests."""
    return "asyncio"


@pytest.fixture(scope="session")
def app():
    """
    Return the FastAPI application under test.

    Scoped to the session so the app is created once per test run.
    The lifespan context is NOT entered here — that happens per-request
    via the AsyncClient fixture.
    """
    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    return create_app()


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Create a test-scoped async database engine.

    Uses NullPool to prevent connection pooling between tests — each
    connection is closed immediately when returned. This ensures the
    per-test transaction rollback pattern works correctly.

    Creates all tables from the ORM metadata before the test session and
    drops them afterward. This is the ONLY place ``create_all``/``drop_all``
    is used; it is explicitly allowed for test setup per CLAUDE.md §10.
    """
    from app.config import get_settings
    from app.database import Base

    # Import all model modules here as they are added so their tables are included
    # in create_all(). Add a line for each new module:
    #   from app.modules.trips.models import TripModel  # noqa: F401
    #   from app.modules.users.models import UserModel  # noqa: F401
    from app.modules.locations.models import Location  # noqa: F401

    settings = get_settings()
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provide a transactional database session that rolls back after each test.

    The session is bound to a connection that has an outer transaction started.
    Any commits made via ``session.flush()`` write to the database within
    the outer transaction. The outer transaction is rolled back at the end of
    the test, so all changes are discarded regardless of whether the test
    called flush or not.

    This gives each test a fully clean database state without recreating
    tables between tests.
    """
    connection = await db_engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    yield session

    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def uow_factory(
    db_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """
    Return an async_sessionmaker configured for the test database.

    Use this when testing use cases or service classes that instantiate
    ``SQLAlchemyUnitOfWork`` internally. The sessions created by this factory
    connect to the test database and are NOT wrapped in the per-test rollback
    transaction — callers are responsible for cleanup.

    For most tests, prefer the ``db_session`` fixture. Use this only when
    the code under test creates its own UoW.
    """
    return async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# ── HTTP client fixture ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide an async HTTP test client for the FastAPI app.

    Uses ASGITransport to call the app in-process without a real server.
    The lifespan context is entered and exited for each test function.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ── Convenience re-exports for test helpers ───────────────────────────────────

__all__ = [
    "anyio_backend",
    "app",
    "client",
    "db_engine",
    "db_session",
    "uow_factory",
]
