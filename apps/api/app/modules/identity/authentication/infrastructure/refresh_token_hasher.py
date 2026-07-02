"""
Sha256RefreshTokenHasher — infrastructure implementation.

Computes the one-way SHA-256 hash of a PlainRefreshToken for database storage.

Design rationale (see ADR-005):
  - SHA-256 chosen over HMAC-SHA256 for refresh tokens because:
      * The plaintext token already has 256 bits of entropy.
      * A 256-bit random token is not susceptible to dictionary attacks,
        making the HMAC key-extension benefit negligible for this use case.
      * SHA-256 is sufficient; Argon2id / bcrypt are for LOW-ENTROPY inputs
        (passwords). Overkill — and slower — for high-entropy tokens.
  - hashlib.sha256 is constant-time in CPython for equal-length inputs
    when called on bytes (implementation note; not a security guarantee).
  - The PlainRefreshToken.value is encoded UTF-8 before hashing; the
    URL-safe base64 alphabet is ASCII-only so encoding is identity.

Usage via DI:
    from app.modules.identity.authentication.infrastructure.dependencies import (
        CurrentRefreshTokenHasher,
    )
"""

from __future__ import annotations

import hashlib

from app.modules.identity.authentication.domain.value_objects.plain_refresh_token import (
    PlainRefreshToken,
)
from app.modules.identity.authentication.domain.value_objects.refresh_token_hash import (
    RefreshTokenHash,
)


class Sha256RefreshTokenHasher:
    """
    SHA-256 hasher for PlainRefreshToken values.

    Implements RefreshTokenHasher protocol. Stateless singleton — safe
    to share across requests.

    The plaintext token is NEVER stored, logged, or passed beyond this method.
    The RefreshTokenHash returned here is the only persistent representation
    of the token.
    """

    def hash(self, token: PlainRefreshToken) -> RefreshTokenHash:
        """
        Compute SHA-256(token.value encoded as UTF-8).

        Returns a RefreshTokenHash (64 lowercase hex characters).
        Safe to store in the database and include in structured log output.
        """
        raw_bytes = token.value.encode("utf-8")
        hex_digest = hashlib.sha256(raw_bytes).hexdigest()
        return RefreshTokenHash(value=hex_digest)
