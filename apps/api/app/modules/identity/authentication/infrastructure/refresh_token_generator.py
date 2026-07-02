"""
SecureRefreshTokenGenerator — infrastructure implementation.

Generates cryptographically secure 256-bit opaque refresh tokens using
Python's secrets module (backed by os.urandom / getrandom syscall).

Security properties:
  - 256 bits of entropy: secrets.token_urlsafe(32) = 32 bytes = 256 bits.
  - URL-safe base64 encoded: 43 characters, no padding, no special chars.
  - Each call produces a statistically independent token.
  - The generator holds no state and stores nothing.

Usage via DI:
    from app.modules.identity.authentication.infrastructure.dependencies import (
        CurrentRefreshTokenGenerator,
    )
"""

from __future__ import annotations

from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)


class SecureRefreshTokenGenerator:
    """
    CSPRNG-backed refresh token generator.

    Implements RefreshTokenGenerator protocol. Stateless singleton — safe
    to share across requests.

    Delegates to PlainRefreshToken.generate() which calls secrets.token_urlsafe(32).
    Defined as a separate class (not just calling generate() directly) so tests
    can inject a deterministic stub that satisfies the RefreshTokenGenerator Protocol.
    """

    def generate(self) -> PlainRefreshToken:
        """
        Generate a cryptographically secure 256-bit URL-safe refresh token.

        Returns a PlainRefreshToken. The raw value must be:
          1. Returned to the client in the HTTP response.
          2. Hashed immediately via RefreshTokenHasher for storage.
          3. Never stored, logged, or passed to any other system as plaintext.
        """
        return PlainRefreshToken.generate()
