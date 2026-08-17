"""ProposalStatus enum and transition helpers."""

from __future__ import annotations

from enum import StrEnum


class ProposalStatus(StrEnum):
    """Lifecycle status of a TripProposal aggregate."""

    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
    EXPIRED = "expired"


# Allowed transitions. ACCEPTED, REJECTED, FAILED, EXPIRED are terminal.
_VALID_TRANSITIONS: dict[ProposalStatus, frozenset[ProposalStatus]] = {
    ProposalStatus.QUEUED: frozenset({ProposalStatus.GENERATING, ProposalStatus.FAILED}),
    ProposalStatus.GENERATING: frozenset({ProposalStatus.READY, ProposalStatus.FAILED}),
    ProposalStatus.READY: frozenset(
        {ProposalStatus.ACCEPTED, ProposalStatus.REJECTED, ProposalStatus.EXPIRED}
    ),
    ProposalStatus.ACCEPTED: frozenset(),
    ProposalStatus.REJECTED: frozenset(),
    ProposalStatus.FAILED: frozenset(),
    ProposalStatus.EXPIRED: frozenset(),
}


def can_transition(from_status: ProposalStatus, to_status: ProposalStatus) -> bool:
    """Return True if transitioning from_status → to_status is permitted."""
    return to_status in _VALID_TRANSITIONS.get(from_status, frozenset())


def valid_next_statuses(status: ProposalStatus) -> frozenset[ProposalStatus]:
    """Return the set of statuses reachable from status in one step."""
    return _VALID_TRANSITIONS.get(status, frozenset())
