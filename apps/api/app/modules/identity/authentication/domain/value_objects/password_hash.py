"""
PasswordHash value object.

Wraps a hashed password string produced by the infrastructure layer.
The domain never hashes, verifies, or compares passwords directly — those
operations belong to PasswordHasher (a domain service interface).

Algorithm-agnostic design:
  The original implementation validated bcrypt's exact format ($2b$...).
  This was changed in TASK-2.2 to be algorithm-agnostic. Rationale:
    - A bcrypt-specific regex prevents migrating to Argon2id or other
      algorithms without modifying the domain model (violates OCP).
    - The domain should not know WHICH algorithm was used — only THAT
      a hash exists and needs to be kept secret.
    - The PasswordHasher.needs_rehash() method, not the value object,
      is responsible for detecting whether a stored hash needs upgrading.

  The replaced validation (bcrypt regex → minimum length) is weaker at
  detecting malformed values, but sufficient: any real hash algorithm
  produces strings far longer than 20 characters; a plaintext password
  short enough to pass would still be an unusual edge case caught by
  PasswordStrengthPolicy's minimum_length.

Security guarantees (unchanged from original):
  - repr() and str() always return '[REDACTED]'.
  - field(repr=False) suppresses field in dataclass __repr__ introspection.
  - The value is never logged, printed, or included in exception messages.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.shared.domain.value_object import ValueObject

# Shorter than the output of any production hashing algorithm:
#   bcrypt: 60 chars, Argon2id: ~95 chars, scrypt: ~88 chars
# A plaintext password shorter than 20 chars would still be caught by
# PasswordStrengthPolicy.minimum_length (typically ≥ 12), but a value
# shorter than 20 almost certainly indicates a programming error.
_MIN_HASH_LENGTH: int = 20


@dataclass(frozen=True)
class PasswordHash(ValueObject):
    """
    An opaque hashed password string produced by PasswordHasher.

    Algorithm-agnostic: accepts bcrypt, Argon2id, scrypt, or any future
    algorithm's output without modification. The algorithm is encoded in
    the hash string itself (e.g., "$2b$..." for bcrypt, "$argon2id$..."
    for Argon2id) — use PasswordHasher.needs_rehash() to detect upgrades.

    Never construct from user input. Obtain exclusively from:
      PasswordHasher.hash(plain_password)

    Raises:
      ValueError: if value is empty or suspiciously short.
        (Programming error — indicates the hasher was not called.)
    """

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("PasswordHash value must not be empty.")
        if len(self.value) < _MIN_HASH_LENGTH:
            raise ValueError(
                f"PasswordHash value is only {len(self.value)} characters — "
                f"must be at least {_MIN_HASH_LENGTH}. "
                "Ensure this is a hashed value, not a plaintext password."
            )

    def __repr__(self) -> str:
        return "PasswordHash([REDACTED])"

    def __str__(self) -> str:
        return "[REDACTED]"
