"""
UUID Provider abstraction — shared kernel.

Decouples use-case code from uuid.uuid4() so that generated IDs are
deterministic in unit tests without monkey-patching the uuid module.

Usage:
    class CreateTripUseCase:
        def __init__(self, uuid_provider: UUIDProvider) -> None:
            self._uuid = uuid_provider

        async def execute(self, ...) -> ...:
            trip_id = TripId(self._uuid.generate())

    # Production:
    use_case = CreateTripUseCase(uuid_provider=StandardUUIDProvider())

    # Tests:
    fixed_id = UUID("00000000-0000-4000-8000-000000000001")
    use_case = CreateTripUseCase(uuid_provider=FixedUUIDProvider([fixed_id]))
"""

from __future__ import annotations

from collections import deque
from typing import Protocol, runtime_checkable
from uuid import UUID, uuid4


@runtime_checkable
class UUIDProvider(Protocol):
    """
    Generates UUIDs for use as entity identifiers.

    The production implementation uses uuid.uuid4() (cryptographically
    random). Test implementations return deterministic sequences.
    """

    def generate(self) -> UUID:
        """Return a new unique identifier."""
        ...


class StandardUUIDProvider:
    """
    Production UUID provider backed by uuid.uuid4().

    Thread-safe: uuid4() is backed by os.urandom() which is thread-safe.
    """

    def generate(self) -> UUID:
        return uuid4()


class FixedUUIDProvider:
    """
    Test double: returns UUIDs from a pre-loaded sequence.

    Raises IndexError (or wraps around, depending on mode) when the
    sequence is exhausted. Use this for tests that need to assert on
    specific entity IDs.

    Usage:
        ids = [UUID("..."), UUID("...")]
        provider = FixedUUIDProvider(ids)
        assert provider.generate() == ids[0]
        assert provider.generate() == ids[1]
    """

    def __init__(self, ids: list[UUID]) -> None:
        self._remaining: deque[UUID] = deque(ids)

    def generate(self) -> UUID:
        if not self._remaining:
            raise IndexError("FixedUUIDProvider exhausted: no more UUIDs in the sequence.")
        return self._remaining.popleft()
