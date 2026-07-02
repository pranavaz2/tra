"""
Travix AI — Shared FastAPI Dependencies

Provides typed dependency aliases used across all route modules.
Import these aliases in route handlers rather than the raw Depends() call
to keep route signatures concise and consistent.

Usage:
    from app.dependencies import DatabaseSession, AppSettings, CurrentClock, AppContext

    @router.get("/trips")
    async def list_trips(db: DatabaseSession, settings: AppSettings) -> ...:
        ...

    @router.post("/trips")
    async def create_trip(db: DatabaseSession, ctx: AppContext) -> ...:
        trip_id = ctx.uuid_provider.generate()
        now = ctx.clock.now()
        ...
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import get_db_session
from app.shared.application.context import ApplicationContext
from app.shared.infrastructure.clock import Clock, SystemClock
from app.shared.infrastructure.random_provider import DefaultRandomProvider, RandomProvider
from app.shared.infrastructure.uuid_provider import DefaultUuidProvider, UuidProvider

# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
"""
Provides a transactional AsyncSession per request.
Commits on handler success; rolls back on any exception.
"""

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

AppSettings = Annotated[Settings, Depends(get_settings)]
"""
Provides the cached Settings singleton.
Equivalent to calling get_settings() but integrates with FastAPI's DI graph
for testability (can be overridden with app.dependency_overrides).
"""

# ---------------------------------------------------------------------------
# Infrastructure provider dependencies
# ---------------------------------------------------------------------------
#
# These singletons are constructed once at DI resolution time.
# In tests, override them via app.dependency_overrides:
#
#   app.dependency_overrides[get_clock] = lambda: FixedClock(test_time)
#   app.dependency_overrides[get_uuid_provider] = lambda: SequentialUuidProvider()


def get_clock() -> Clock:
    """Return the system clock (UTC). Override in tests with FixedClock."""
    return SystemClock()


def get_uuid_provider() -> UuidProvider:
    """Return the default UUID provider. Override in tests with SequentialUuidProvider."""
    return DefaultUuidProvider()


def get_random_provider() -> RandomProvider:
    """Return the default random provider. Override in tests with SeededRandomProvider."""
    return DefaultRandomProvider()


CurrentClock = Annotated[Clock, Depends(get_clock)]
"""Provides the current UTC clock. Testable via dependency_overrides."""

CurrentUuidProvider = Annotated[UuidProvider, Depends(get_uuid_provider)]
"""Provides UUID generation. Testable via dependency_overrides."""

CurrentRandomProvider = Annotated[RandomProvider, Depends(get_random_provider)]
"""Provides random value generation. Testable via dependency_overrides."""

# ---------------------------------------------------------------------------
# ApplicationContext — unified context for use cases
# ---------------------------------------------------------------------------
#
# Bundles clock, uuid_provider, and random_provider into a single dependency.
# Use this in route handlers that call use case classes, or anywhere all
# three infrastructure concerns are needed together.
#
# In tests, override get_app_context:
#   fixed_ctx = ApplicationContext.testing(fixed_time=test_time, seed=42)
#   app.dependency_overrides[get_app_context] = lambda: fixed_ctx


def get_app_context(
    clock: CurrentClock,
    uuid_provider: CurrentUuidProvider,
    random_provider: CurrentRandomProvider,
) -> ApplicationContext:
    """Compose the three provider dependencies into an ApplicationContext."""
    return ApplicationContext(
        clock=clock,
        uuid_provider=uuid_provider,
        random_provider=random_provider,
    )


AppContext = Annotated[ApplicationContext, Depends(get_app_context)]
"""
Provides a fully-wired ApplicationContext for the current request.

Use this in route handlers that pass context to use case classes:

    @router.post("/trips")
    async def create_trip(
        payload: TripCreateRequest,
        db: DatabaseSession,
        ctx: AppContext,
    ) -> TripResponse:
        result = await CreateTripUseCase(repo=..., ctx=ctx).execute(payload)
        ...
"""
