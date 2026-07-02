"""
Travix AI — ApplicationContext

A single-value object that bundles the infrastructure dependencies that
cross-cut every application use case: clock, UUID generation, randomness.

Why a context object?
  - FastAPI can inject each provider separately as typed dependencies, but
    ARQ background workers have no FastAPI DI. They need a way to receive
    the same set of dependencies without duplicating the wiring.
  - Grouping them in one dataclass makes use-case constructors clean:
        def __init__(self, ctx: ApplicationContext, repo: TripRepository)
    instead of:
        def __init__(self, clock: Clock, uuid: UuidProvider, rand: RandomProvider, ...)

  - In tests, a single `ApplicationContext.testing()` call produces a
    deterministic context without any production dependencies.

Usage — FastAPI (individual dependency injection, see dependencies.py):
    async def create_trip(ctx: AppContext, repo: TripRepository): ...

Usage — ARQ worker (constructed once at worker startup):
    context = ApplicationContext.default()
    async def process_job(ctx: dict) -> None:
        app_ctx: ApplicationContext = ctx["app_context"]
        trip_id = app_ctx.uuid_provider.generate()
        ...

Usage — tests (deterministic):
    ctx = ApplicationContext.testing(seed=42)
    assert ctx.clock.now() == datetime(2024, 1, 1, tzinfo=UTC)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.shared.infrastructure.clock import Clock, FixedClock, SystemClock
from app.shared.infrastructure.random_provider import (
    DefaultRandomProvider,
    RandomProvider,
    SeededRandomProvider,
)
from app.shared.infrastructure.uuid_provider import (
    DefaultUuidProvider,
    SequentialUuidProvider,
    UuidProvider,
)


@dataclass(frozen=True)
class ApplicationContext:
    """
    Immutable container for shared infrastructure dependencies.

    All fields are Protocols — the concrete implementations are injected
    at construction time, keeping use cases decoupled from infrastructure.
    """

    clock: Clock
    uuid_provider: UuidProvider
    random_provider: RandomProvider

    @classmethod
    def default(cls) -> "ApplicationContext":
        """
        Production context: real system clock, real UUIDs, cryptographic randomness.

        Use in:
          - FastAPI application startup (app.state.context = ApplicationContext.default())
          - ARQ worker startup (ctx["app_context"] = ApplicationContext.default())
        """
        return cls(
            clock=SystemClock(),
            uuid_provider=DefaultUuidProvider(),
            random_provider=DefaultRandomProvider(),
        )

    @classmethod
    def testing(
        cls,
        *,
        fixed_time: datetime | None = None,
        seed: int = 0,
        uuid_start: int = 1,
    ) -> "ApplicationContext":
        """
        Deterministic test context.

        Args:
            fixed_time: Fixed UTC time returned by clock.now().
                        Defaults to 2024-01-01T00:00:00Z if not provided.
            seed:       Seed for the random provider (default 0).
            uuid_start: Starting integer for sequential UUID generation (default 1).

        Usage:
            ctx = ApplicationContext.testing()
            ctx = ApplicationContext.testing(
                fixed_time=datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC),
                seed=99,
                uuid_start=100,
            )
        """
        _DEFAULT_TEST_TIME = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        return cls(
            clock=FixedClock(fixed_time if fixed_time is not None else _DEFAULT_TEST_TIME),
            uuid_provider=SequentialUuidProvider(start=uuid_start),
            random_provider=SeededRandomProvider(seed=seed),
        )
