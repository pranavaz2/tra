"""ProposalId — unique identity for the TripProposal aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.shared.domain.value_object import ValueObject


@dataclass(frozen=True)
class ProposalId(ValueObject):
    """Wraps a UUID as the TripProposal aggregate's primary identity."""

    value: UUID

    @classmethod
    def generate(cls) -> ProposalId:
        """Create a new random ProposalId."""
        return cls(value=uuid4())

    @classmethod
    def from_str(cls, raw: str) -> ProposalId:
        """Parse a UUID string. Raises ValueError on bad format."""
        return cls(value=UUID(raw))

    def __str__(self) -> str:
        return str(self.value)
