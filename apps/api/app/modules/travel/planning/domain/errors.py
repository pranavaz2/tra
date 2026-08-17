"""Domain-specific error types for the Travel Planning context."""

from __future__ import annotations

from uuid import UUID

from app.shared.domain.errors import ConflictError, DomainError, NotFoundError


class ProposalNotFoundError(NotFoundError):
    """The requested TripProposal does not exist."""

    code = "proposal_not_found"

    def __init__(self, proposal_id: UUID | str) -> None:
        super().__init__("proposal", proposal_id)


class InvalidProposalStatusTransitionError(DomainError):
    """The requested status transition is not permitted."""

    code = "invalid_proposal_status_transition"

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Cannot transition trip proposal from '{from_status}' to '{to_status}'."
        )
        self.from_status = from_status
        self.to_status = to_status


class ProposalAlreadyDeletedError(DomainError):
    """An operation was attempted on a soft-deleted proposal."""

    code = "proposal_already_deleted"

    def __init__(self) -> None:
        super().__init__("This trip proposal has been deleted and cannot be mutated.")


class ActiveProposalExistsError(ConflictError):
    """An active proposal already exists for the trip."""

    code = "active_proposal_exists"

    def __init__(self, trip_id: str) -> None:
        super().__init__(
            f"Trip '{trip_id}' already has an active proposal in progress."
        )
        self.trip_id = trip_id
