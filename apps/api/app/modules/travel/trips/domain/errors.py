"""Trip-specific domain errors."""

from __future__ import annotations

from app.shared.domain.errors import ApplicationError, DomainError


class TripNotFoundError(ApplicationError):
    """No trip exists with the given ID."""

    code = "trip_not_found"

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip '{trip_id}' not found.")
        self.trip_id = trip_id


class InvalidTripStatusTransitionError(DomainError):
    """The requested status transition is not permitted."""

    code = "invalid_trip_status_transition"

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Cannot transition trip from '{from_status}' to '{to_status}'."
        )
        self.from_status = from_status
        self.to_status = to_status


class TripAlreadyDeletedError(DomainError):
    """The trip has already been soft-deleted."""

    code = "trip_already_deleted"

    def __init__(self) -> None:
        super().__init__("This trip has already been deleted.")
