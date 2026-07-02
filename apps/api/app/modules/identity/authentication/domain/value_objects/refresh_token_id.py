"""Refresh token identity value object — wraps a UUID primary key."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class RefreshTokenId(ValueObject):
    """
    Opaque identifier for a refresh token.

    Each token rotation generates a new RefreshTokenId. The infrastructure
    layer stores the mapping (id → hashed token bytes) and uses this id
    to look up and revoke tokens in Redis.
    """

    value: UUID

    @classmethod
    def generate(cls) -> "RefreshTokenId":
        """Create a new random RefreshTokenId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> "RefreshTokenId":
        """Parse a UUID string into a RefreshTokenId. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
