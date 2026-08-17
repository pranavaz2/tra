"""TripProposal aggregate root."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.planning.domain.errors import (
    InvalidProposalStatusTransitionError,
    ProposalAlreadyDeletedError,
)
from app.modules.travel.planning.domain.events.proposal_events import (
    ProposalAccepted,
    ProposalExpired,
    ProposalFailed,
    ProposalGenerationStarted,
    ProposalReady,
    ProposalRejected,
    ProposalRequested,
)
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.planning.domain.value_objects.proposal_status import (
    ProposalStatus,
    can_transition,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot


@dataclass(kw_only=True, eq=False)
class TripProposal(AggregateRoot[ProposalId]):
    """
    TripProposal aggregate root.

    Manages the lifecycle of an AI-generated trip proposal.

    Fields:
        entity_id:      ProposalId — aggregate primary identity.
        trip_id:        TripId — reference to the trip being planned.
        owner_id:       UserId — user who owns this proposal (matches trip owner).
        preferences:    PlanningPreferences — inputs for AI generation.
        status:         ProposalStatus — current stage in lifecycle.
        result:         PlanningResult | None — generated plan when READY.
        failure_reason: str | None — error details if status is FAILED.
        expires_at:     datetime | None — proposal TTL (checked at query/command).
        version:        int — concurrency version.
        deleted_at:     datetime | None — non-None indicates soft deletion.
    """

    trip_id: TripId
    owner_id: UserId
    preferences: PlanningPreferences
    status: ProposalStatus = ProposalStatus.QUEUED
    result: PlanningResult | None = None
    failure_reason: str | None = None
    expires_at: datetime | None = None
    version: int = 1
    deleted_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                            #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        proposal_id: ProposalId,
        trip_id: TripId,
        owner_id: UserId,
        preferences: PlanningPreferences,
    ) -> TripProposal:
        """Create a new TripProposal in QUEUED status and emit ProposalRequested."""
        proposal = cls(
            entity_id=proposal_id,
            trip_id=trip_id,
            owner_id=owner_id,
            preferences=preferences,
            status=ProposalStatus.QUEUED,
            version=1,
        )
        proposal.push_event(
            ProposalRequested(
                aggregate_id=str(proposal_id),
                proposal_id=str(proposal_id),
                trip_id=str(trip_id),
                owner_id=str(owner_id),
                destination=preferences.destination,
                duration_days=preferences.duration_days,
                budget_level=preferences.budget_level,
                interests=preferences.interests,
                travel_style=preferences.travel_style,
                special_requirements=preferences.special_requirements,
            )
        )
        return proposal

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                  #
    # ------------------------------------------------------------------ #

    @property
    def proposal_id(self) -> ProposalId:
        """Alias for entity_id with the concrete ProposalId type."""
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                      #
    # ------------------------------------------------------------------ #

    @property
    def is_deleted(self) -> bool:
        """True if this proposal has been soft-deleted."""
        return self.deleted_at is not None

    @property
    def is_expired(self) -> bool:
        """True if the proposal has expired based on current UTC time."""
        if self.status != ProposalStatus.READY or self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at

    # ------------------------------------------------------------------ #
    # Private helpers                                                    #
    # ------------------------------------------------------------------ #

    def _guard_not_deleted(self) -> None:
        if self.is_deleted:
            raise ProposalAlreadyDeletedError()

    def _mutate(self) -> None:
        """Increment version and touch audit timestamp."""
        self.version += 1
        self.touch()

    def _transition_to(self, new_status: ProposalStatus) -> None:
        """Transition status or raise error if transition is invalid."""
        if not can_transition(self.status, new_status):
            raise InvalidProposalStatusTransitionError(
                from_status=self.status.value, to_status=new_status.value
            )
        self.status = new_status

    # ------------------------------------------------------------------ #
    # Mutations                                                          #
    # ------------------------------------------------------------------ #

    def start_generation(self) -> None:
        """Transition proposal from QUEUED to GENERATING."""
        self._guard_not_deleted()
        self._transition_to(ProposalStatus.GENERATING)
        self._mutate()
        self.push_event(
            ProposalGenerationStarted(
                aggregate_id=str(self.proposal_id),
                proposal_id=str(self.proposal_id),
                trip_id=str(self.trip_id),
            )
        )

    def complete_generation(self, result: PlanningResult, expires_at: datetime) -> None:
        """Complete generation, populate result and expires_at, transition to READY."""
        self._guard_not_deleted()
        self._transition_to(ProposalStatus.READY)
        self.result = result
        self.expires_at = expires_at
        self._mutate()
        self.push_event(
            ProposalReady(
                aggregate_id=str(self.proposal_id),
                proposal_id=str(self.proposal_id),
                trip_id=str(self.trip_id),
                expires_at=expires_at,
            )
        )

    def accept(self) -> None:
        """Accept the ready proposal."""
        self._guard_not_deleted()
        # Check lazy expiry first
        if self.is_expired:
            self.expire()
            raise InvalidProposalStatusTransitionError(
                from_status=ProposalStatus.EXPIRED.value,
                to_status=ProposalStatus.ACCEPTED.value,
            )

        self._transition_to(ProposalStatus.ACCEPTED)
        self._mutate()
        self.push_event(
            ProposalAccepted(
                aggregate_id=str(self.proposal_id),
                proposal_id=str(self.proposal_id),
                trip_id=str(self.trip_id),
                owner_id=str(self.owner_id),
            )
        )

    def reject(self) -> None:
        """Reject the ready proposal."""
        self._guard_not_deleted()
        if self.is_expired:
            self.expire()
            raise InvalidProposalStatusTransitionError(
                from_status=ProposalStatus.EXPIRED.value,
                to_status=ProposalStatus.REJECTED.value,
            )

        self._transition_to(ProposalStatus.REJECTED)
        self._mutate()
        self.push_event(
            ProposalRejected(
                aggregate_id=str(self.proposal_id),
                proposal_id=str(self.proposal_id),
                trip_id=str(self.trip_id),
            )
        )

    def expire(self) -> None:
        """Expire the proposal."""
        self._guard_not_deleted()
        self._transition_to(ProposalStatus.EXPIRED)
        self._mutate()
        self.push_event(
            ProposalExpired(
                aggregate_id=str(self.proposal_id),
                proposal_id=str(self.proposal_id),
                trip_id=str(self.trip_id),
            )
        )

    def fail(self, reason: str) -> None:
        """Fail the proposal generation (or mark as superseded)."""
        self._guard_not_deleted()
        self._transition_to(ProposalStatus.FAILED)
        self.failure_reason = reason
        self._mutate()
        self.push_event(
            ProposalFailed(
                aggregate_id=str(self.proposal_id),
                proposal_id=str(self.proposal_id),
                trip_id=str(self.trip_id),
                reason=reason,
            )
        )

    def delete(self) -> None:
        """Soft-delete the proposal."""
        self._guard_not_deleted()
        self.deleted_at = datetime.now(UTC)
        self._mutate()
        # Since delete is not a core lifecycle status transition in the state machine,
        # but a system soft-delete, we don't change status to a terminal state but rather
        # just record deleted_at. There is no specific ProposalDeleted event in design,
        # but we can emit a fail or just keep it simple. Let's keep it simple and just mutate.
