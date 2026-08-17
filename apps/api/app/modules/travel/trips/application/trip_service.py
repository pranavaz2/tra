"""
TripService — application-layer orchestrator for all trip use cases.

Responsibilities:
  - Parse and validate raw inputs from commands/queries (string → domain types).
  - Enforce authorization (requester must be the trip owner).
  - Orchestrate domain aggregate mutations within a Unit of Work transaction.
  - Publish domain events after each successful commit (best-effort).
  - Return typed Result values — never raise for expected failures.

Architecture constraints (CLAUDE.md):
  - NO FastAPI imports. Zero web-framework dependencies.
  - NO SQLAlchemy imports. All persistence through ITripRepository.
  - NO HTTP exceptions. Expected failures are Failure(TravixError).
  - Business logic (invariants, transitions) lives in the Trip domain aggregate.
    This service ORCHESTRATES — it does not enforce business rules itself.

Transaction model:
  Command methods (create, update, delete) open the Unit of Work as an
  async context manager:

      async with self._uow:
          <repository mutations>
          await self._uow.commit()   # explicit commit on success

  If any step raises an exception, __aexit__ calls rollback(). Expected
  failures (TravixError) are caught and returned as Failure(e). Unexpected
  infrastructure errors are caught, logged, and returned as
  Failure(InfrastructureError(...)).

  Query methods (get, list) call the repository directly without a UoW
  because they perform no mutations and need no commit boundary.

Event publishing:
  Domain events are popped from the aggregate AFTER a successful commit
  and published via the injected EventPublisher. A publish failure must NOT
  appear to roll back the already-committed write — it is logged and
  execution continues (best-effort delivery).

Authorization model (current):
  Only the trip's owner can read, update, or delete their trips.
  Future: collaborative trips will extend this to TripCollaboration members.

Cursor pagination (list_trips):
  The service decodes the opaque cursor (base64url TripId) received from the
  client, requests limit+1 items from the repository to detect the next page,
  then encodes a new cursor from the last item's trip_id.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import date

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.application.commands import (
    CreateTripCommand,
    DeleteTripCommand,
    UpdateTripCommand,
)
from app.modules.travel.trips.application.dtos import (
    CreateTripResult,
    DeleteTripResult,
    GetTripResult,
    ListTripsResult,
    TripListPage,
    TripSummary,
    UpdateTripResult,
)
from app.modules.travel.trips.application.queries import GetTripQuery, ListTripsQuery
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider

logger = logging.getLogger(__name__)


class TripService:
    """
    Application service for trip use cases.

    Accepts ITripRepository, UnitOfWork, EventPublisher, and UUIDProvider
    as constructor dependencies — all Protocols, no concrete infrastructure
    types. The DI layer (dependencies.py) wires concrete implementations.

    For in-memory testing:
        service = TripService(
            repository=InMemoryTripRepository(),
            unit_of_work=InMemoryUnitOfWork(),
            event_publisher=LoggingEventPublisher(),
            uuid_provider=FixedUUIDProvider([uuid1, uuid2, ...]),
        )
    """

    def __init__(
        self,
        *,
        repository: ITripRepository,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
    ) -> None:
        self._repository = repository
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid_provider = uuid_provider

    # ---------------------------------------------------------------------- #
    # Commands — mutate state                                                  #
    # ---------------------------------------------------------------------- #

    async def create_trip(self, command: CreateTripCommand) -> CreateTripResult:
        """
        Create a new Trip aggregate and persist it.

        Steps:
          1. Parse owner_id into UserId.
          2. Build and validate domain value objects (title, privacy, date range).
          3. Generate a new TripId.
          4. Construct the Trip aggregate via Trip.create() (emits TripCreated).
          5. Persist within a Unit of Work transaction.
          6. Publish domain events after commit.
          7. Return Success(TripSummary).

        Returns:
            Success(TripSummary)           — trip was created.
            Failure(ValidationError)       — invalid owner_id, title, privacy,
                                            or date range.
            Failure(InfrastructureError)   — persistence or event-publish failure.
        """
        logger.info("Creating trip", extra={"owner_id": command.owner_id})

        # Parse and validate domain types before any I/O.
        try:
            owner_id = UserId.from_str(command.owner_id)
            title = TripTitle(value=command.title)
            privacy = TripPrivacy(command.privacy)
            date_range = _build_date_range(
                command.departure_date, command.return_date, command.is_date_flexible
            )
        except TravixError as exc:
            return Failure(exc)
        except ValueError as exc:
            return Failure(ValidationError(str(exc), field="owner_id", value=command.owner_id))

        trip_id = TripId(value=self._uuid_provider.generate())
        trip = Trip.create(
            trip_id=trip_id,
            owner_id=owner_id,
            title=title,
            privacy=privacy,
            date_range=date_range,
        )

        try:
            async with self._uow:
                await self._repository.save(trip)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            logger.error(
                "create_trip: persistence failed",
                extra={"trip_id": str(trip_id), "reason": str(exc)},
            )
            return Failure(InfrastructureError("Failed to save trip.", cause=exc))

        await self._publish(trip.pop_events(), context="create_trip")

        logger.info("Trip created", extra={"trip_id": str(trip_id)})
        return Success(self._to_dto(trip))

    async def update_trip(self, command: UpdateTripCommand) -> UpdateTripResult:
        """
        Apply one or more mutations to an existing Trip.

        Only fields explicitly set in the command are applied:
          - command.title → trip.rename(title)
          - command.privacy → trip.change_privacy(privacy)
          - command.new_status → trip.transition_to(status)
          - command.update_dates=True → trip.reschedule(date_range)

        When no fields are set and update_dates=False, the operation is
        a no-op (save is still called but flushes no changes).

        The entire load–mutate–save sequence runs inside a single Unit of
        Work to guarantee atomicity and enable optimistic locking.

        Returns:
            Success(TripSummary)                       — update succeeded.
            Failure(TripNotFoundError)                 — trip not found or deleted.
            Failure(ForbiddenError)                    — requester is not the owner.
            Failure(ValidationError)                   — invalid ID or field value.
            Failure(InvalidTripStatusTransitionError)  — illegal status transition.
            Failure(InfrastructureError)               — persistence failure.
        """
        logger.info(
            "Updating trip",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )

        # Parse and validate all input fields before opening the UoW.
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            new_title: TripTitle | None = (
                TripTitle(value=command.title) if command.title is not None else None
            )
            new_privacy: TripPrivacy | None = (
                TripPrivacy(command.privacy) if command.privacy is not None else None
            )
            new_status: TripStatus | None = (
                TripStatus(command.new_status) if command.new_status is not None else None
            )
            # Build date range only when update_dates=True.
            # _build_date_range returns None when departure_date is None
            # (meaning "clear the date range").
            new_date_range: TripDateRange | None = None
            should_reschedule = command.update_dates
            if should_reschedule:
                new_date_range = _build_date_range(
                    command.departure_date, command.return_date, command.is_date_flexible
                )
        except TravixError as exc:
            return Failure(exc)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        trip: Trip
        try:
            async with self._uow:
                trip = await self._repository.find_by_id(trip_id)
                if trip is None or trip.is_deleted:
                    return Failure(TripNotFoundError(str(trip_id)))
                if trip.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this trip."))

                # Apply mutations in a stable order: title → privacy → dates → status.
                # Status last because a transition may constrain what operations are
                # still valid (e.g. ARCHIVED → no further mutations).
                if new_title is not None:
                    trip.rename(new_title)
                if new_privacy is not None:
                    trip.change_privacy(new_privacy)
                if should_reschedule:
                    trip.reschedule(new_date_range)
                if new_status is not None:
                    trip.transition_to(new_status)

                await self._repository.save(trip)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            logger.error(
                "update_trip: persistence failed",
                extra={"trip_id": command.trip_id, "reason": str(exc)},
            )
            return Failure(InfrastructureError("Failed to update trip.", cause=exc))

        await self._publish(trip.pop_events(), context="update_trip")

        logger.info("Trip updated", extra={"trip_id": str(trip_id)})
        return Success(self._to_dto(trip))

    async def delete_trip(self, command: DeleteTripCommand) -> DeleteTripResult:
        """
        Soft-delete a trip (sets deleted_at, emits TripDeleted).

        The trip record is NOT physically removed. The presentation layer
        must NOT expose the trip after deletion. Hard deletion for GDPR
        erasure is handled separately via ITripRepository.delete().

        Returns:
            Success(None)              — trip was soft-deleted.
            Failure(TripNotFoundError) — trip not found or already deleted.
            Failure(ForbiddenError)    — requester is not the owner.
            Failure(ValidationError)   — invalid ID format.
            Failure(InfrastructureError) — persistence failure.
        """
        logger.info(
            "Deleting trip",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )

        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        trip: Trip
        try:
            async with self._uow:
                trip = await self._repository.find_by_id(trip_id)
                if trip is None or trip.is_deleted:
                    return Failure(TripNotFoundError(str(trip_id)))
                if trip.owner_id != requester_id:
                    return Failure(ForbiddenError("You do not have access to this trip."))

                trip.delete()
                await self._repository.save(trip)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            logger.error(
                "delete_trip: persistence failed",
                extra={"trip_id": command.trip_id, "reason": str(exc)},
            )
            return Failure(InfrastructureError("Failed to delete trip.", cause=exc))

        await self._publish(trip.pop_events(), context="delete_trip")

        logger.info("Trip deleted", extra={"trip_id": str(trip_id)})
        return Success(None)

    # ---------------------------------------------------------------------- #
    # Queries — read-only, no UoW                                             #
    # ---------------------------------------------------------------------- #

    async def get_trip(self, query: GetTripQuery) -> GetTripResult:
        """
        Load a single trip by ID.

        Soft-deleted trips are treated as not found (returns TripNotFoundError).
        Authorization: requester must be the trip's owner.

        Returns:
            Success(TripSummary)       — trip found and authorised.
            Failure(TripNotFoundError) — trip not found or soft-deleted.
            Failure(ForbiddenError)    — requester is not the owner.
            Failure(ValidationError)   — invalid ID format.
            Failure(InfrastructureError) — repository failure.
        """
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        try:
            trip = await self._repository.find_by_id(trip_id)
        except Exception as exc:
            logger.error(
                "get_trip: repository failure",
                extra={"trip_id": query.trip_id, "reason": str(exc)},
            )
            return Failure(InfrastructureError("Failed to load trip.", cause=exc))

        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))
        if trip.owner_id != requester_id:
            return Failure(ForbiddenError("You do not have access to this trip."))

        return Success(self._to_dto(trip))

    async def list_trips(self, query: ListTripsQuery) -> ListTripsResult:
        """
        List a user's trips with cursor-based pagination.

        Returns non-deleted trips owned by owner_id, newest-first.
        Requests limit+1 items from the repository to detect whether a
        next page exists, then encodes the last item's trip_id as the
        next_cursor.

        Authorization: requester must be the same as owner_id.

        Returns:
            Success(TripListPage)       — page of results (may be empty).
            Failure(ForbiddenError)     — requester is not the owner.
            Failure(ValidationError)    — invalid ID, cursor, or status_filter.
            Failure(InfrastructureError) — repository failure.
        """
        try:
            owner_id = UserId.from_str(query.owner_id)
            requester_id = UserId.from_str(query.requester_id)
        except ValueError as exc:
            return Failure(ValidationError(str(exc)))

        if owner_id != requester_id:
            return Failure(ForbiddenError("You can only list your own trips."))

        # Decode cursor (base64url TripId string → TripId domain object).
        after_id: TripId | None = None
        if query.cursor is not None:
            try:
                after_id = TripId.from_str(decode_cursor(query.cursor))
            except Exception:
                return Failure(
                    ValidationError(
                        "Invalid pagination cursor.",
                        field="cursor",
                        value=query.cursor,
                    )
                )

        # Validate optional status filter.
        status_filter: TripStatus | None = None
        if query.status_filter is not None:
            try:
                status_filter = TripStatus(query.status_filter)
            except ValueError:
                return Failure(
                    ValidationError(
                        f"Invalid status filter: '{query.status_filter}'. "
                        f"Valid values: {[s.value for s in TripStatus]}.",
                        field="status_filter",
                        value=query.status_filter,
                    )
                )

        # Request one extra item to detect whether a next page exists.
        fetch_limit = query.limit + 1

        try:
            trips = await self._repository.find_by_owner(
                owner_id,
                limit=fetch_limit,
                after_id=after_id,
                status_filter=status_filter,
            )
        except Exception as exc:
            logger.error(
                "list_trips: repository failure",
                extra={"owner_id": query.owner_id, "reason": str(exc)},
            )
            return Failure(InfrastructureError("Failed to list trips.", cause=exc))

        has_more = len(trips) > query.limit
        if has_more:
            trips = trips[: query.limit]

        next_cursor: str | None = None
        if has_more and trips:
            next_cursor = encode_cursor(str(trips[-1].trip_id))

        return Success(
            TripListPage(
                items=tuple(self._to_dto(t) for t in trips),
                next_cursor=next_cursor,
                has_more=has_more,
                limit=query.limit,
            )
        )

    # ---------------------------------------------------------------------- #
    # Private helpers                                                          #
    # ---------------------------------------------------------------------- #

    def _to_dto(self, trip: Trip) -> TripSummary:
        """Map a Trip domain entity to a TripSummary DTO."""
        dr = trip.date_range
        return TripSummary(
            trip_id=trip.trip_id,
            owner_id=trip.owner_id,
            title=str(trip.title),
            status=trip.status,
            privacy=trip.privacy,
            departure_date=dr.departure_date if dr is not None else None,
            return_date=dr.return_date if dr is not None else None,
            is_date_flexible=dr.is_flexible if dr is not None else False,
            version=trip.version,
            created_at=trip.created_at,
            updated_at=trip.updated_at,
            deleted_at=trip.deleted_at,
        )

    async def _publish(self, events: Sequence[DomainEvent], *, context: str) -> None:
        """
        Publish domain events after a successful commit.

        Best-effort: publish failures are logged but do NOT propagate.
        A publish failure must not appear to roll back a committed transaction.
        """
        if not events:
            return
        try:
            await self._event_publisher.publish(events)
        except Exception as exc:
            logger.error(
                "Event publication failed",
                extra={
                    "context": context,
                    "event_count": len(events),
                    "reason": str(exc),
                },
            )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _build_date_range(
    departure_date: date | None,
    return_date: date | None,
    is_flexible: bool,
) -> TripDateRange | None:
    """
    Construct a TripDateRange from optional departure and return dates.

    Returns None when departure_date is None (meaning: no dates set or
    "clear the existing date range"). Validation of date ordering (return
    >= departure) is performed by TripDateRange.__post_init__.
    """
    if departure_date is None:
        return None
    return TripDateRange(
        departure_date=departure_date,
        return_date=return_date,
        is_flexible=is_flexible,
    )
