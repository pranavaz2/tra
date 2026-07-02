"""
Travix AI — UUID Provider Abstraction

Wraps UUID generation behind an interface so that code generating IDs
can be tested with predictable, deterministic values.

Why not call uuid4() directly?
  - Code that calls uuid4() directly produces unpredictable IDs in tests.
    Test assertions like `assert response["id"] == expected_id` become
    impossible without this abstraction.
  - A UuidProvider dependency can be replaced in tests with a
    SequentialUuidProvider that returns UUIDs in a predictable order.

Usage — in application code:
    from app.shared.infrastructure.uuid_provider import UuidProvider
    from app.dependencies import CurrentUuidProvider

    async def create_trip(provider: CurrentUuidProvider, ...) -> TripResponse:
        trip_id = provider.generate()
        ...

Usage — in tests (predictable IDs):
    from app.shared.infrastructure.uuid_provider import SequentialUuidProvider
    provider = SequentialUuidProvider()
    assert provider.generate() == UUID("00000000-0000-0000-0000-000000000001")
    assert provider.generate() == UUID("00000000-0000-0000-0000-000000000002")

Usage — in tests (fixed single ID):
    from app.shared.infrastructure.uuid_provider import FixedUuidProvider
    provider = FixedUuidProvider(UUID("12345678-1234-5678-1234-567812345678"))
    assert provider.generate() == UUID("12345678-1234-5678-1234-567812345678")
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4


@runtime_checkable
class UuidProvider(Protocol):
    """Generates UUID values."""

    def generate(self) -> UUID:
        """Return a new unique UUID."""
        ...


class DefaultUuidProvider:
    """Production implementation: generates random UUIDs (uuid4)."""

    def generate(self) -> UUID:
        return uuid4()


class FixedUuidProvider:
    """
    Test implementation: always returns the same UUID.

    Use when the exact ID value matters and must be asserted in tests.
    """

    def __init__(self, fixed_id: UUID) -> None:
        self._fixed = fixed_id

    def generate(self) -> UUID:
        return self._fixed


class SequentialUuidProvider:
    """
    Test implementation: returns UUIDs with incrementing integer suffixes.

    The sequence starts at 1 and each call increments by 1:
        00000000-0000-0000-0000-000000000001
        00000000-0000-0000-0000-000000000002
        ...

    This makes test assertions readable and ordered without random noise.
    """

    def __init__(self, start: int = 1) -> None:
        self._counter = start - 1

    def generate(self) -> UUID:
        self._counter += 1
        return UUID(int=self._counter)

    def reset(self, start: int = 1) -> None:
        """Reset the counter (useful in test setUp/tearDown)."""
        self._counter = start - 1
