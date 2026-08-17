"""Travel Planning application commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestProposalCommand:
    """Command to request a new travel planning proposal."""

    trip_id: str
    requester_id: str
    destination: str
    duration_days: int
    budget_level: str
    interests: list[str]
    travel_style: str
    special_requirements: str


@dataclass(frozen=True)
class AcceptProposalCommand:
    """Command to accept an generated travel proposal."""

    proposal_id: str
    requester_id: str


@dataclass(frozen=True)
class RejectProposalCommand:
    """Command to reject a generated travel proposal."""

    proposal_id: str
    requester_id: str
