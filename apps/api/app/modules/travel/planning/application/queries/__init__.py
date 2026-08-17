"""Travel Planning application queries."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE


@dataclass(frozen=True)
class GetProposalQuery:
    """Query to retrieve a proposal by its ID."""

    proposal_id: str
    requester_id: str


@dataclass(frozen=True)
class GetProposalByTripQuery:
    """Query to retrieve the latest proposal for a given trip ID."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class ListProposalsQuery:
    """Query to list proposals for an owner with cursor-based pagination."""

    owner_id: str
    requester_id: str
    limit: int = DEFAULT_PAGE_SIZE
    cursor: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "limit", min(max(1, self.limit), MAX_PAGE_SIZE))
