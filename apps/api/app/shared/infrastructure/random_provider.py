"""
Travix AI — Random Provider Abstraction

Wraps random value generation behind an interface for deterministic testing.

Why not call random.* directly?
  - Random values in tests make assertions non-deterministic and can cause
    intermittent failures.
  - A SeededRandomProvider with a fixed seed produces the same sequence
    on every test run.

Usage — in application code:
    from app.shared.infrastructure.random_provider import RandomProvider
    from app.dependencies import CurrentRandomProvider

    async def generate_invite_code(rand: CurrentRandomProvider) -> str:
        return rand.token_hex(8)  # 16-character hex string, testable

Usage — in tests (seeded, reproducible):
    from app.shared.infrastructure.random_provider import SeededRandomProvider
    rand = SeededRandomProvider(seed=42)
    code1 = rand.token_hex(8)  # always the same value for seed=42
"""

from __future__ import annotations

import random
import secrets
import string
from typing import Protocol, runtime_checkable


@runtime_checkable
class RandomProvider(Protocol):
    """Provides random value generation."""

    def token_hex(self, nbytes: int = 32) -> str:
        """Return a random hex string with nbytes bytes of randomness."""
        ...

    def token_urlsafe(self, nbytes: int = 32) -> str:
        """Return a random URL-safe Base64-encoded string."""
        ...

    def choice(self, seq: list[str]) -> str:
        """Return a random element from a non-empty sequence."""
        ...

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        ...


class DefaultRandomProvider:
    """
    Production implementation: uses the secrets module for cryptographic
    strength where applicable, and random for non-security-sensitive calls.
    """

    def token_hex(self, nbytes: int = 32) -> str:
        return secrets.token_hex(nbytes)

    def token_urlsafe(self, nbytes: int = 32) -> str:
        return secrets.token_urlsafe(nbytes)

    def choice(self, seq: list[str]) -> str:
        return secrets.choice(seq)

    def randint(self, a: int, b: int) -> int:
        return secrets.randbelow(b - a + 1) + a


class SeededRandomProvider:
    """
    Test implementation: uses a seeded random.Random instance.

    Produces the same sequence for the same seed, making tests reproducible.
    NOT cryptographically secure — use only in tests.
    """

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)  # noqa: S311 — not used for security

    def token_hex(self, nbytes: int = 32) -> str:
        return "".join(
            self._rng.choices(string.hexdigits[:16], k=nbytes * 2)
        )

    def token_urlsafe(self, nbytes: int = 32) -> str:
        alphabet = string.ascii_letters + string.digits + "-_"
        # Match secrets.token_urlsafe length approximation
        length = (nbytes * 4 + 2) // 3
        return "".join(self._rng.choices(alphabet, k=length))

    def choice(self, seq: list[str]) -> str:
        return self._rng.choice(seq)

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def reset(self, seed: int = 0) -> None:
        """Re-seed the RNG (useful in test setUp)."""
        self._rng.seed(seed)
