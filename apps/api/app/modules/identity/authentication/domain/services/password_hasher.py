"""
PasswordHasher domain service interface.

This is a PRIMARY PORT (in hexagonal architecture terms): the domain defines
what it needs from a hashing capability, and the infrastructure layer
provides a concrete adapter (bcrypt, Argon2id, PKDF2, etc.).

Design decisions:
  - All methods are SYNCHRONOUS. Hashing is CPU-bound, not I/O-bound.
    The infrastructure adapter is responsible for thread-pool offloading
    (asyncio.to_thread) if the calling context is async. The domain
    interface should not assume async infrastructure.
  - Methods accept and return domain types only (str, PasswordHash).
    No algorithm-specific parameters cross this boundary — those are
    encapsulated in the concrete adapter's constructor configuration.
  - needs_rehash() enables zero-downtime algorithm migration: old hashes
    are transparently upgraded on next successful login without requiring
    a forced password reset.

Algorithm migration path (without breaking any domain code):
  bcrypt (current)
    → Argon2id (next)
    → Passkeys / platform authenticators (passwordless)

Each migration requires only a new concrete adapter class and a config
change — the domain, application, and API layers remain untouched.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.identity.authentication.domain.value_objects.password_hash import PasswordHash


@runtime_checkable
class PasswordHasher(Protocol):
    """
    Port for password hashing and verification.

    Implementations live in the infrastructure layer and may wrap:
      - passlib (bcrypt, Argon2)
      - cryptography library
      - external HSM / KMS (for regulated environments)

    The domain depends ONLY on this interface.
    """

    def hash(self, plain_password: str) -> PasswordHash:
        """
        Hash a plaintext password and return an opaque PasswordHash.

        Implementations must:
          - Use a cryptographically secure, slow hashing algorithm.
          - Embed a unique salt per call (no rainbow table attacks).
          - Never log or return the plaintext password.
          - Raise PasswordHashingError if the hashing operation fails.

        Args:
            plain_password: The raw password from user input.
                            NEVER stored, logged, or passed further.

        Returns:
            An opaque PasswordHash wrapping the encoded hash string.

        Raises:
            PasswordHashingError: if the underlying hashing operation fails.
        """
        ...

    def verify(self, plain_password: str, password_hash: PasswordHash) -> bool:
        """
        Verify a plaintext password against a stored hash.

        Implementations must:
          - Use constant-time comparison to prevent timing attacks.
          - Never raise exceptions for incorrect passwords — return False.
          - Raise PasswordHashingError only for infrastructure failures
            (corrupted hash, unavailable library, etc.).

        Args:
            plain_password: The password provided by the user at login.
            password_hash:  The stored hash from AuthenticationCredential.

        Returns:
            True if the password matches the hash, False otherwise.

        Raises:
            PasswordHashingError: if the hash is structurally corrupt or
                the underlying library is unavailable.
        """
        ...

    def needs_rehash(self, password_hash: PasswordHash) -> bool:
        """
        Return True if this hash should be upgraded on next login.

        Used for transparent algorithm migration: the application checks
        this on every successful login. If True, it re-hashes the plaintext
        (available at login time) with the current algorithm and saves the
        new hash — no forced password reset required.

        Upgrade triggers (implementation-defined):
          - Hash produced by a weaker algorithm (bcrypt → Argon2id).
          - Work factor below the current minimum (cost factor 10 → 12).
          - Deprecated algorithm (MD5, SHA1, unsalted SHA256).

        Args:
            password_hash: The currently-stored hash.

        Returns:
            True if the hash should be upgraded, False if it is current.
        """
        ...
