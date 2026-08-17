"""
Trip aggregate root.

A Trip is the central entity of the Travel context. Every other Travel
module references a TripId but does not own the Trip itself.

Invariants enforced by this aggregate:
  - Title: 1–100 characters after stripping whitespace (enforced in TripTitle).
  - Date range: return_date >= departure_date when provided (enforced in TripDateRange).
  - Status transitions: only permitted transitions are allowed (see TripStatus).
  - A soft-deleted trip cannot be mutated further.

Event lifecycle:
  - Mutations call push_event() to record what happened.
  - The application layer calls pop_events() after a successful save()
    and dispatches the events to subscribers.
  - Events are never dispatched from within the aggregate or repository.

Design note:
  owner_id uses UserId from the Identity context. The Travel context is
  permitted to import Identity value objects (UserId, SessionId) as a
  cross-context shared value — no other identity types are imported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.errors import (
    InvalidTripStatusTransitionError,
    TripAlreadyDeletedError,
)
from app.modules.travel.trips.domain.events.trip_events import (
    TripCreated,
    TripDeleted,
    TripStatusChanged,
    TripUpdated,
)
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import (
    TripStatus,
    can_transition,
)
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.aggregate import AggregateRoot


@dataclass(kw_only=True, eq=False)
class Trip(AggregateRoot[TripId]):
    """
    Trip aggregate root.

    Fields:
        entity_id:   TripId — the aggregate's unique identity.
        owner_id:    UserId — the user who created and owns this trip.
        title:       TripTitle — human-readable name (1–100 chars).
        status:      TripStatus — current lifecycle state.
        privacy:     TripPrivacy — who can see this trip.
        date_range:  TripDateRange | None — planned travel window.
        version:     int — optimistic concurrency counter; incremented on
                     every mutation.
        deleted_at:  datetime | None — non-None indicates soft delete.

    Inherited from Entity:
        created_at, updated_at — managed via touch() on every mutation.
    """

    owner_id: UserId
    title: TripTitle
    status: TripStatus
    privacy: TripPrivacy
    date_range: TripDateRange | None = None
    version: int = 1
    deleted_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        trip_id: TripId,
        owner_id: UserId,
        title: TripTitle,
        privacy: TripPrivacy = TripPrivacy.PRIVATE,
        date_range: TripDateRange | None = None,
    ) -> "Trip":
        """
        Create a new Trip and emit TripCreated.

        New trips always start in DRAFT status. The owner is set here and
        is immutable — ownership transfer is not supported.
        """
        trip = cls(
            entity_id=trip_id,
            owner_id=owner_id,
            title=title,
            status=TripStatus.DRAFT,
            privacy=privacy,
            date_range=date_range,
            version=1,
        )
        trip.push_event(
            TripCreated(
                aggregate_id=str(trip_id),
                trip_id=str(trip_id),
                owner_id=str(owner_id),
                title=str(title),
                status=trip.status.value,
                privacy=trip.privacy.value,
                departure_date=date_range.departure_date if date_range else None,
                return_date=date_range.return_date if date_range else None,
            )
        )
        return trip

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                    #
    # ------------------------------------------------------------------ #

    @property
    def trip_id(self) -> TripId:
        """Alias for entity_id with the concrete TripId type."""
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_deleted(self) -> bool:
        """True if this trip has been soft-deleted."""
        return self.deleted_at is not None

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _guard_not_deleted(self) -> None:
        if self.is_deleted:
            raise TripAlreadyDeletedError()

    def _mutate(self) -> None:
        """Increment the version counter and refresh updated_at."""
        self.version += 1
        self.touch()

    # ------------------------------------------------------------------ #
    # Mutations                                                            #
    # ------------------------------------------------------------------ #

    def rename(self, new_title: TripTitle) -> None:
        """
        Change the trip's title and emit TripUpdated.

        Args:
            new_title: Validated TripTitle (1–100 chars, stripped).

        Raises:
            TripAlreadyDeletedError: if the trip has been soft-deleted.
        """
        self._guard_not_deleted()
        self.title = new_title
        self._mutate()
        self.push_event(
            TripUpdated(
                aggregate_id=str(self.trip_id),
                trip_id=str(self.trip_id),
                changed_fields=("title",),
            )
        )

    def reschedule(self, new_date_range: TripDateRange | None) -> None:
        """
        Update the planned travel window and emit TripUpdated.

        Pass None to clear the date range (open-ended trip).

        Args:
            new_date_range: Validated TripDateRange, or None.

        Raises:
            TripAlreadyDeletedError: if the trip has been soft-deleted.
        """
        self._guard_not_deleted()
        self.date_range = new_date_range
        self._mutate()
        self.push_event(
            TripUpdated(
                aggregate_id=str(self.trip_id),
                trip_id=str(self.trip_id),
                changed_fields=("date_range",),
            )
        )

    def change_privacy(self, new_privacy: TripPrivacy) -> None:
        """
        Change who can see this trip and emit TripUpdated.

        Raises:
            TripAlreadyDeletedError: if the trip has been soft-deleted.
        """
        self._guard_not_deleted()
        self.privacy = new_privacy
        self._mutate()
        self.push_event(
            TripUpdated(
                aggregate_id=str(self.trip_id),
                trip_id=str(self.trip_id),
                changed_fields=("privacy",),
            )
        )

    def transition_to(self, new_status: TripStatus) -> None:
        """
        Advance the trip lifecycle to new_status and emit TripStatusChanged.

        Valid transitions:
            DRAFT     → PLANNED, ARCHIVED
            PLANNED   → ACTIVE, DRAFT, ARCHIVED
            ACTIVE    → COMPLETED, ARCHIVED
            COMPLETED → ARCHIVED
            ARCHIVED  → (terminal — no outbound transitions)

        Args:
            new_status: The desired next status.

        Raises:
            TripAlreadyDeletedError:          if the trip has been soft-deleted.
            InvalidTripStatusTransitionError: if the transition is not allowed.
        """
        self._guard_not_deleted()
        if not can_transition(self.status, new_status):
            raise InvalidTripStatusTransitionError(
                from_status=self.status.value,
                to_status=new_status.value,
            )
        old_status = self.status
        self.status = new_status
        self._mutate()
        self.push_event(
            TripStatusChanged(
                aggregate_id=str(self.trip_id),
                trip_id=str(self.trip_id),
                old_status=old_status.value,
                new_status=new_status.value,
            )
        )

    def delete(self) -> None:
        """
        Soft-delete this trip and emit TripDeleted.

        Sets deleted_at to the current UTC time. Subsequent calls to any
        mutation method (including delete itself) will raise TripAlreadyDeletedError.

        Raises:
            TripAlreadyDeletedError: if the trip has already been soft-deleted.
        """
        self._guard_not_deleted()
        now = datetime.now(UTC)
        self.deleted_at = now
        self._mutate()
        self.push_event(
            TripDeleted(
                aggregate_id=str(self.trip_id),
                trip_id=str(self.trip_id),
                owner_id=str(self.owner_id),
                deleted_at=now,
            )
        )
