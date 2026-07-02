"""
Travix AI — Clock Abstraction

Wraps the current UTC time behind an interface so that application code
can be tested with deterministic, controlled time instead of the real clock.

Why not call datetime.now(UTC) directly?
  - Code that calls datetime.now() directly cannot be deterministically tested
    for time-sensitive behaviour (expiry, scheduling, TTL checks).
  - A Clock dependency can be replaced in tests with a FixedClock that
    always returns the same timestamp, making tests reproducible.

Usage — in application code:
    from app.shared.infrastructure.clock import Clock
    from app.dependencies import CurrentClock

    @router.post("/trips")
    async def create_trip(clock: CurrentClock) -> TripResponse:
        now = clock.now()  # UTC datetime, testable
        ...

Usage — in tests:
    from app.shared.infrastructure.clock import FixedClock
    fixed_clock = FixedClock(datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC))
    # Inject via FastAPI dependency override or ApplicationContext
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provides the current UTC datetime."""

    def now(self) -> datetime:
        """Return the current UTC datetime with timezone info."""
        ...


class SystemClock:
    """
    Production implementation: uses datetime.now(UTC).

    This is the default implementation injected by FastAPI DI.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """
    Test implementation: always returns a fixed datetime.

    Use in tests where time-dependent behaviour must be deterministic.

        fixed = FixedClock(datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC))
        assert some_service.compute_expiry(fixed) == datetime(2024, 6, 1, 12, 15, 0, tzinfo=UTC)
    """

    def __init__(self, fixed_time: datetime) -> None:
        if fixed_time.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime (use UTC).")
        self._fixed = fixed_time

    def now(self) -> datetime:
        return self._fixed
