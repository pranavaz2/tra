"""
Clock abstraction — shared kernel.

Decouples application and domain code from wall-clock time so that
time-sensitive logic is fully testable without patching datetime.now().

Usage:
    class MyService:
        def __init__(self, clock: Clock) -> None:
            self._clock = clock

        def is_token_fresh(self, issued_at: datetime) -> bool:
            return (self._clock.now() - issued_at).seconds < 300

    # Production:
    service = MyService(clock=SystemClock())

    # Tests:
    frozen = FrozenClock(datetime(2025, 1, 1, 12, 0, tzinfo=UTC))
    service = MyService(clock=frozen)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """
    Provides the current time.

    All returned datetimes are timezone-aware (UTC).
    The system implementation delegates to datetime.now(UTC).
    Test implementations return a fixed or advancing value.
    """

    def now(self) -> datetime:
        """Return the current UTC datetime."""
        ...


class SystemClock:
    """
    Real-time clock backed by datetime.now(UTC).

    This is the production implementation. Inject into application
    services via dependency injection.
    """

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """
    Test double: always returns the same instant.

    Useful when you need deterministic time in unit tests without
    patching datetime globally.

    Usage:
        clock = FrozenClock(datetime(2025, 6, 1, 0, 0, tzinfo=UTC))
        assert clock.now() == datetime(2025, 6, 1, 0, 0, tzinfo=UTC)
    """

    def __init__(self, frozen_at: datetime) -> None:
        if frozen_at.tzinfo is None:
            raise ValueError("FrozenClock requires a timezone-aware datetime.")
        self._frozen_at = frozen_at

    def now(self) -> datetime:
        return self._frozen_at
