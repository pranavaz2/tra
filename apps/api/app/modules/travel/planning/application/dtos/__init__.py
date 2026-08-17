"""Travel Planning application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.planning.domain.entities.trip_proposal import TripProposal
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.planning.domain.value_objects.proposal_status import (
    ProposalStatus,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.result import Result


@dataclass(frozen=True)
class ProposalSummary:
    """Snapshot of a TripProposal aggregate's current state."""

    proposal_id: ProposalId
    trip_id: TripId
    owner_id: UserId
    preferences: PlanningPreferences
    status: ProposalStatus
    result: PlanningResult | None
    failure_reason: str | None
    expires_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @classmethod
    def from_aggregate(cls, proposal: TripProposal) -> ProposalSummary:
        """Convert a TripProposal aggregate to a ProposalSummary DTO."""
        return cls(
            proposal_id=proposal.proposal_id,
            trip_id=proposal.trip_id,
            owner_id=proposal.owner_id,
            preferences=proposal.preferences,
            status=proposal.status,
            result=proposal.result,
            failure_reason=proposal.failure_reason,
            expires_at=proposal.expires_at,
            version=proposal.version,
            created_at=proposal.created_at,
            updated_at=proposal.updated_at,
            deleted_at=proposal.deleted_at,
        )


@dataclass(frozen=True)
class ProposalListPage:
    """A single page of paginated proposal results."""

    items: tuple[ProposalSummary, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


# Result type aliases
RequestProposalResult: TypeAlias = "Result[ProposalSummary]"  # noqa: UP040
AcceptProposalResult: TypeAlias = "Result[ProposalSummary]"  # noqa: UP040
RejectProposalResult: TypeAlias = "Result[ProposalSummary]"  # noqa: UP040
GetProposalResult: TypeAlias = "Result[ProposalSummary]"  # noqa: UP040
ListProposalsResult: TypeAlias = "Result[ProposalListPage]"  # noqa: UP040
