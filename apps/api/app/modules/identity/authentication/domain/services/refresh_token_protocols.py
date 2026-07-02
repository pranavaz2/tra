"""
Domain service protocols for refresh token generation and hashing.

These are DOMAIN-LAYER interfaces — they define what the domain needs
from the infrastructure layer, not how it is implemented. The concrete
implementations (SecureRefreshTokenGenerator, Sha256RefreshTokenHasher)
live in the infrastructure layer and are injected via FastAPI DI.

Design rationale:
  - RefreshTokenGenerator: isolates the CSPRNG from the domain. Tests can
    inject a deterministic generator to produce predictable tokens.
  - RefreshTokenHasher: isolates the hashing algorithm. If we ever need to
    migrate from SHA-256 to a keyed-HMAC approach, only the infrastructure
    changes — the domain interface stays the same.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)


@runtime_checkable
class RefreshTokenGenerator(Protocol):
    """
    Generates cryptographically secure opaque refresh tokens.

    Contract:
      - Every call produces a statistically unique 256-bit URL-safe token.
      - The implementation MUST use a CSPRNG (os.urandom or equivalent).
      - The generated token MUST NOT be stored by the generator.
    """

    def generate(self) -> PlainRefreshToken:
        """
        Generate a new 256-bit opaque refresh token.

        Returns a PlainRefreshToken whose value must be returned to the client
        and immediately hashed for storage. Never store the return value in a DB.
        """
        ...


@runtime_checkable
class RefreshTokenHasher(Protocol):
    """
    Computes the one-way hash of a PlainRefreshToken for database storage.

    Contract:
      - hash() is deterministic: same input → same output.
      - hash() is one-way: the original token cannot be recovered from the hash.
      - Implementations MUST NOT log or store the PlainRefreshToken's value.
    """

    def hash(self, token: PlainRefreshToken) -> RefreshTokenHash:
        """
        Compute the hash of token for database storage.

        The returned RefreshTokenHash is safe to store and log.
        The input PlainRefreshToken must never be stored or logged.
        """
        ...
