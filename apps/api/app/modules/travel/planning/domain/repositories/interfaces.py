"""ITripProposalRepository — domain persistence interface for TripProposal aggregate."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.planning.domain.entities.trip_proposal import TripProposal
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


@runtime_checkable
class ITripProposalRepository(Protocol):
    """
    Persistence interface for TripProposal aggregates.

    Implementations:
      - SQLAlchemyTripProposalRepository (infrastructure layer) — production.
      - InMemoryTripProposalRepository (tests) — used in unit tests.
    """

    async def find_by_id(self, proposal_id: ProposalId) -> TripProposal | None:
        """
        Return the TripProposal with the given ID, or None if not found.

        Soft-deleted proposals ARE returned.
        """
        ...

    async def find_by_trip_id(self, trip_id: TripId) -> TripProposal | None:
        """
        Return the latest non-deleted TripProposal for the given trip ID, or None.
        """
        ...

    async def find_active_by_trip_id(self, trip_id: TripId) -> TripProposal | None:
        """
        Return any in-flight (status = QUEUED or GENERATING) proposal for the trip.
        """
        ...

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: ProposalId | None = None,
    ) -> list[TripProposal]:
        """
        Return up to limit non-deleted proposals owned by owner_id.

        Ordered by created_at descending (newest first).
        """
        ...

    async def save(self, proposal: TripProposal) -> None:
        """
        Persist a new or updated proposal (upsert semantics).

        Must flush to database, but NOT commit.
        """
        ...

    async def delete(self, proposal_id: ProposalId) -> None:
        """
        Hard-delete the proposal record with the given ID.
        """
        ...

    async def exists(self, proposal_id: ProposalId) -> bool:
        """Return True if a non-deleted proposal exists with this ID."""
        ...
