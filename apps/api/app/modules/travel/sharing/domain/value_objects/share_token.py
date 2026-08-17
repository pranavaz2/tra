"""ShareToken value object."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from app.shared.domain.value_object import ValueObject

_TOKEN_BYTES = 32  # 32 bytes = 64 hex characters


@dataclass(frozen=True)
class ShareToken(ValueObject):
    """
    Opaque URL-safe token for public trip sharing.

    Generated with :func:`secrets.token_hex` to ensure cryptographic
    randomness. The value is a 64-character lowercase hexadecimal string.
    """

    value: str

    @classmethod
    def generate(cls) -> ShareToken:
        """Generate a new cryptographically-secure share token."""
        return cls(value=secrets.token_hex(_TOKEN_BYTES))

    def __str__(self) -> str:
        return self.value
