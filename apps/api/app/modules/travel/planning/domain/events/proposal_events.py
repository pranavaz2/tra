"""TripProposal domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class ProposalRequested(DomainEvent):
    """Emitted when a new TripProposal is requested and queued."""

    proposal_id: str
    trip_id: str
    owner_id: str
    destination: str
    duration_days: int
    budget_level: str
    interests: tuple[str, ...]
    travel_style: str
    special_requirements: str


@dataclass(frozen=True, kw_only=True)
class ProposalGenerationStarted(DomainEvent):
    """Emitted when the AI starts generating the trip proposal."""

    proposal_id: str
    trip_id: str


@dataclass(frozen=True, kw_only=True)
class ProposalReady(DomainEvent):
    """Emitted when the AI finishes generating the trip proposal successfully."""

    proposal_id: str
    trip_id: str
    expires_at: datetime


@dataclass(frozen=True, kw_only=True)
class ProposalAccepted(DomainEvent):
    """Emitted when the user accepts the proposal."""

    proposal_id: str
    trip_id: str
    owner_id: str


@dataclass(frozen=True, kw_only=True)
class ProposalRejected(DomainEvent):
    """Emitted when the user rejects the proposal."""

    proposal_id: str
    trip_id: str


@dataclass(frozen=True, kw_only=True)
class ProposalExpired(DomainEvent):
    """Emitted when a proposal passes its expiration time without being accepted/rejected."""

    proposal_id: str
    trip_id: str


@dataclass(frozen=True, kw_only=True)
class ProposalFailed(DomainEvent):
    """Emitted when proposal generation fails or is superseded by a newer proposal."""

    proposal_id: str
    trip_id: str
    reason: str
