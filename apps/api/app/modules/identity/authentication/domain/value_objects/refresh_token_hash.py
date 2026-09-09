"""
RefreshTokenHash value object.

Represents the SHA-256 hex digest of a PlainRefreshToken.
This is the value stored in the database for lookup.

Design rationale:
  - One-way: original token cannot be recovered from the hash.
  - Constant length (64 hex chars): safe for indexed column equality.
  - Safe to log for request correlation (prefix shown in repr).
  - ValidationError on construction prevents corrupt hashes entering the domain.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.shared.domain.errors import ValidationError
from app.shared.domain.value_object import ValueObject

_SHA256_HEX_LENGTH = 64
_VALID_HEX_CHARS = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class RefreshTokenHash(ValueObject):
    """
    SHA-256 hex digest of a PlainRefreshToken (64 lowercase hex characters).

    Safe to store in the database and include in structured log output for
    correlation. Cannot be reversed to the original token value.

    Use RefreshTokenHasher (infrastructure service) to produce instances from
    a PlainRefreshToken — do not hash manually in application code.
    """

    value: str  # 64-char lowercase hex string

    def __post_init__(self) -> None:
        if len(self.value) != _SHA256_HEX_LENGTH:
            raise ValidationError(
                f"RefreshTokenHash must be {_SHA256_HEX_LENGTH} hex characters, "
                f"got {len(self.value)}.",
                field="refresh_token_hash",
            )
        if not all(c in _VALID_HEX_CHARS for c in self.value):
            raise ValidationError(
                "RefreshTokenHash must be lowercase hexadecimal.",
                field="refresh_token_hash",
            )

    def __repr__(self) -> str:
        # Show first 16 chars as a correlation handle; not enough to reverse the hash.
        return f"RefreshTokenHash(sha256:{self.value[:16]}...)"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_hex(cls, hex_str: str) -> "RefreshTokenHash":
        """Parse and normalise a hex string into a RefreshTokenHash."""
        return cls(value=hex_str.lower())
