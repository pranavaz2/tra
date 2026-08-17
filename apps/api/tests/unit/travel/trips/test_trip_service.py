"""Unit tests for TripService using in-memory test doubles."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.core.pagination import decode_cursor
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.unit_of_work import (
    InMemoryUnitOfWork,
)
from app.modules.travel.trips.application.commands import (
    CreateTripCommand,
    DeleteTripCommand,
    UpdateTripCommand,
)
from app.modules.travel.trips.application.dtos import TripListPage, TripSummary
from app.modules.travel.trips.application.queries import GetTripQuery, ListTripsQuery
from app.modules.travel.trips.application.trip_service import TripService
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.errors import (
    TripAlreadyDeletedError,
    TripNotFoundError,
)
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.errors import ForbiddenError, InfrastructureError, ValidationError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.uuid_provider import FixedUUIDProvider


# ─────────────────────────────────────────────────────────────────────────────
# Test doubles
# ─────────────────────────────────────────────────────────────────────────────


class InMemoryTripRepository:
    """
    In-memory ITripRepository for service unit tests.

    Stores Trip objects by TripId.value (UUID). Implements cursor-based
    pagination by sorting on (created_at DESC, trip_id DESC) and filtering
    for items "after" the cursor position.
    """

    def __init__(self) -> None:
        self._store: dict[UUID, Trip] = {}

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self._store.get(trip_id.value)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: TripId | None = None,
        status_filter: TripStatus | None = None,
    ) -> list[Trip]:
        trips = [
            t
            for t in self._store.values()
            if t.owner_id == owner_id and not t.is_deleted
        ]
        if status_filter is not None:
            trips = [t for t in trips if t.status == status_filter]
        trips.sort(key=lambda t: (t.created_at, str(t.trip_id)), reverse=True)
        if after_id is not None:
            cursor_trip = self._store.get(after_id.value)
            if cursor_trip is not None:

                def _after(t: Trip) -> bool:
                    if t.created_at < cursor_trip.created_at:
                        return True
                    if t.created_at == cursor_trip.created_at:
                        return str(t.trip_id) < str(cursor_trip.trip_id)
                    return False

                trips = [t for t in trips if _after(t)]
        return trips[:limit]

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        return [
            t
            for t in self._store.values()
            if t.owner_id == user_id
            and not t.is_deleted
            and t.status in (TripStatus.PLANNED, TripStatus.ACTIVE)
        ]

    async def save(self, trip: Trip) -> None:
        self._store[trip.trip_id.value] = trip

    async def delete(self, trip_id: TripId) -> None:
        self._store.pop(trip_id.value, None)

    async def exists(self, trip_id: TripId) -> bool:
        trip = self._store.get(trip_id.value)
        return trip is not None and not trip.is_deleted

    async def exists_with_title(self, owner_id: UserId, title: TripTitle) -> bool:
        norm = str(title).lower()
        return any(
            t.owner_id == owner_id and not t.is_deleted and str(t.title).lower() == norm
            for t in self._store.values()
        )


class _InMemoryEventPublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


class _FailingRepository(InMemoryTripRepository):
    """Repository that raises on save() to simulate infrastructure failures."""

    async def save(self, trip: Trip) -> None:
        raise RuntimeError("DB connection lost")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


OWNER_ID = str(uuid.uuid4())
OTHER_OWNER_ID = str(uuid.uuid4())
FIXED_TRIP_UUID = uuid.UUID("00000000-0000-4000-8000-000000000001")


def _make_service(
    repo: ITripRepository | None = None,
    *,
    trip_uuid: UUID = FIXED_TRIP_UUID,
    publisher: _InMemoryEventPublisher | None = None,
    uow: InMemoryUnitOfWork | None = None,
) -> tuple[TripService, InMemoryTripRepository, _InMemoryEventPublisher]:
    real_repo = repo if repo is not None else InMemoryTripRepository()
    pub = publisher or _InMemoryEventPublisher()
    real_uow = uow or InMemoryUnitOfWork()
    service = TripService(
        repository=real_repo,
        unit_of_work=real_uow,
        event_publisher=pub,
        uuid_provider=FixedUUIDProvider([trip_uuid]),
    )
    return service, real_repo, pub  # type: ignore[return-value]


async def _create_and_save_trip(
    repo: InMemoryTripRepository,
    *,
    owner_id: str = OWNER_ID,
    title: str = "Test Trip",
    status: TripStatus = TripStatus.DRAFT,
    created_at: datetime | None = None,
) -> Trip:
    """Helper: build a trip domain object and persist it directly in the repo."""
    trip = Trip.create(
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=UserId.from_str(owner_id),
        title=TripTitle(value=title),
    )
    if created_at is not None:
        trip.created_at = created_at
    if status != TripStatus.DRAFT:
        object.__setattr__(trip, "status", status)
    trip.pop_events()  # discard domain events from setup
    await repo.save(trip)
    return trip


# ─────────────────────────────────────────────────────────────────────────────
# create_trip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_trip_success() -> None:
    service, repo, _ = _make_service()
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Lisbon Trip")
    result = await service.create_trip(cmd)
    assert isinstance(result, Success)
    summary = result.value
    assert isinstance(summary, TripSummary)
    assert summary.title == "Lisbon Trip"
    assert summary.status == TripStatus.DRAFT
    assert summary.privacy == TripPrivacy.PRIVATE


@pytest.mark.asyncio
async def test_create_trip_uses_provided_privacy() -> None:
    service, _, _ = _make_service()
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Trip", privacy="public")
    result = await service.create_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.privacy == TripPrivacy.PUBLIC


@pytest.mark.asyncio
async def test_create_trip_sets_dates_when_provided() -> None:
    service, _, _ = _make_service()
    cmd = CreateTripCommand(
        owner_id=OWNER_ID,
        title="Trip",
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 7),
    )
    result = await service.create_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.departure_date == date(2027, 6, 1)
    assert result.value.return_date == date(2027, 6, 7)


@pytest.mark.asyncio
async def test_create_trip_empty_title_fails() -> None:
    service, _, _ = _make_service()
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="")
    result = await service.create_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValidationError)


@pytest.mark.asyncio
async def test_create_trip_title_too_long_fails() -> None:
    service, _, _ = _make_service()
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="X" * 101)
    result = await service.create_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValidationError)


@pytest.mark.asyncio
async def test_create_trip_invalid_privacy_fails() -> None:
    service, _, _ = _make_service()
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Trip", privacy="invalid_value")
    result = await service.create_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, (ValidationError, Exception))


@pytest.mark.asyncio
async def test_create_trip_return_date_before_departure_fails() -> None:
    service, _, _ = _make_service()
    cmd = CreateTripCommand(
        owner_id=OWNER_ID,
        title="Trip",
        departure_date=date(2027, 6, 10),
        return_date=date(2027, 6, 5),  # before departure
    )
    result = await service.create_trip(cmd)
    assert isinstance(result, Failure)


@pytest.mark.asyncio
async def test_create_trip_persists_to_repository() -> None:
    service, repo, _ = _make_service()
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Persisted Trip")
    result = await service.create_trip(cmd)
    assert isinstance(result, Success)
    stored = await repo.find_by_id(result.value.trip_id)
    assert stored is not None
    assert str(stored.title) == "Persisted Trip"


@pytest.mark.asyncio
async def test_create_trip_publishes_event() -> None:
    pub = _InMemoryEventPublisher()
    service, _, _ = _make_service(publisher=pub)
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Event Trip")
    await service.create_trip(cmd)
    assert len(pub.published) == 1


@pytest.mark.asyncio
async def test_create_trip_commits_uow() -> None:
    uow = InMemoryUnitOfWork()
    service, _, _ = _make_service(uow=uow)
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Trip")
    await service.create_trip(cmd)
    assert uow.committed


@pytest.mark.asyncio
async def test_create_trip_infrastructure_error_returns_failure() -> None:
    failing_repo = _FailingRepository()
    service, _, _ = _make_service(repo=failing_repo)
    cmd = CreateTripCommand(owner_id=OWNER_ID, title="Trip")
    result = await service.create_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, InfrastructureError)


# ─────────────────────────────────────────────────────────────────────────────
# update_trip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_trip_title() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id), requester_id=OWNER_ID, title="New Title"
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.title == "New Title"


@pytest.mark.asyncio
async def test_update_trip_privacy() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id), requester_id=OWNER_ID, privacy="public"
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.privacy == TripPrivacy.PUBLIC


@pytest.mark.asyncio
async def test_update_trip_valid_status_transition() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id), requester_id=OWNER_ID, new_status="planned"
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.status == TripStatus.PLANNED


@pytest.mark.asyncio
async def test_update_trip_invalid_status_transition() -> None:
    from app.modules.travel.trips.domain.errors import InvalidTripStatusTransitionError

    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)  # starts as DRAFT
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id),
        requester_id=OWNER_ID,
        new_status="completed",  # DRAFT → COMPLETED is invalid
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, InvalidTripStatusTransitionError)


@pytest.mark.asyncio
async def test_update_trip_sets_date_range_when_update_dates_true() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id),
        requester_id=OWNER_ID,
        update_dates=True,
        departure_date=date(2027, 8, 1),
        return_date=date(2027, 8, 10),
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.departure_date == date(2027, 8, 1)
    assert result.value.return_date == date(2027, 8, 10)


@pytest.mark.asyncio
async def test_update_trip_clears_date_range_when_update_dates_true_no_date() -> None:
    service, repo, _ = _make_service()
    from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange

    trip = await _create_and_save_trip(repo)
    trip.reschedule(
        TripDateRange(departure_date=date(2027, 8, 1), return_date=None, is_flexible=False)
    )
    trip.pop_events()
    await repo.save(trip)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id),
        requester_id=OWNER_ID,
        update_dates=True,
        departure_date=None,  # clear
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.departure_date is None


@pytest.mark.asyncio
async def test_update_trip_leaves_dates_unchanged_when_update_dates_false() -> None:
    from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange

    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    trip.reschedule(
        TripDateRange(departure_date=date(2027, 8, 1), return_date=None, is_flexible=False)
    )
    trip.pop_events()
    await repo.save(trip)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id),
        requester_id=OWNER_ID,
        update_dates=False,
        departure_date=date(2027, 12, 1),  # ignored because update_dates=False
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Success)
    assert result.value.departure_date == date(2027, 8, 1)  # unchanged


@pytest.mark.asyncio
async def test_update_trip_not_found() -> None:
    service, _, _ = _make_service()
    cmd = UpdateTripCommand(
        trip_id=str(uuid.uuid4()), requester_id=OWNER_ID, title="X"
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, TripNotFoundError)


@pytest.mark.asyncio
async def test_update_trip_forbidden_wrong_owner() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id),
        requester_id=OTHER_OWNER_ID,  # not the owner
        title="X",
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_update_deleted_trip_returns_not_found() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    trip.delete()
    trip.pop_events()
    await repo.save(trip)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id), requester_id=OWNER_ID, title="X"
    )
    result = await service.update_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, TripNotFoundError)


@pytest.mark.asyncio
async def test_update_trip_publishes_events() -> None:
    pub = _InMemoryEventPublisher()
    service, repo, _ = _make_service(publisher=pub)
    trip = await _create_and_save_trip(repo)
    cmd = UpdateTripCommand(
        trip_id=str(trip.trip_id), requester_id=OWNER_ID, title="New Title"
    )
    await service.update_trip(cmd)
    assert len(pub.published) >= 1


# ─────────────────────────────────────────────────────────────────────────────
# delete_trip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_trip_success() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = DeleteTripCommand(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    result = await service.delete_trip(cmd)
    assert isinstance(result, Success)
    assert result.value is None


@pytest.mark.asyncio
async def test_delete_trip_marks_trip_as_deleted() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = DeleteTripCommand(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    await service.delete_trip(cmd)
    stored = await repo.find_by_id(trip.trip_id)
    assert stored is not None
    assert stored.is_deleted


@pytest.mark.asyncio
async def test_delete_trip_not_found() -> None:
    service, _, _ = _make_service()
    cmd = DeleteTripCommand(trip_id=str(uuid.uuid4()), requester_id=OWNER_ID)
    result = await service.delete_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, TripNotFoundError)


@pytest.mark.asyncio
async def test_delete_trip_forbidden_wrong_owner() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    cmd = DeleteTripCommand(trip_id=str(trip.trip_id), requester_id=OTHER_OWNER_ID)
    result = await service.delete_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_delete_already_deleted_trip_returns_not_found() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    trip.delete()
    trip.pop_events()
    await repo.save(trip)
    cmd = DeleteTripCommand(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    result = await service.delete_trip(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, TripNotFoundError)


@pytest.mark.asyncio
async def test_delete_trip_publishes_event() -> None:
    pub = _InMemoryEventPublisher()
    service, repo, _ = _make_service(publisher=pub)
    trip = await _create_and_save_trip(repo)
    cmd = DeleteTripCommand(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    await service.delete_trip(cmd)
    assert len(pub.published) >= 1


@pytest.mark.asyncio
async def test_delete_trip_commits_uow() -> None:
    uow = InMemoryUnitOfWork()
    service, repo, _ = _make_service(uow=uow)
    trip = await _create_and_save_trip(repo)
    cmd = DeleteTripCommand(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    await service.delete_trip(cmd)
    assert uow.committed


# ─────────────────────────────────────────────────────────────────────────────
# get_trip
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_trip_success() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo, title="My Trip")
    query = GetTripQuery(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    result = await service.get_trip(query)
    assert isinstance(result, Success)
    assert result.value.title == "My Trip"


@pytest.mark.asyncio
async def test_get_trip_not_found() -> None:
    service, _, _ = _make_service()
    query = GetTripQuery(trip_id=str(uuid.uuid4()), requester_id=OWNER_ID)
    result = await service.get_trip(query)
    assert isinstance(result, Failure)
    assert isinstance(result.error, TripNotFoundError)


@pytest.mark.asyncio
async def test_get_deleted_trip_returns_not_found() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    trip.delete()
    trip.pop_events()
    await repo.save(trip)
    query = GetTripQuery(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    result = await service.get_trip(query)
    assert isinstance(result, Failure)
    assert isinstance(result.error, TripNotFoundError)


@pytest.mark.asyncio
async def test_get_trip_forbidden_wrong_owner() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo)
    query = GetTripQuery(trip_id=str(trip.trip_id), requester_id=OTHER_OWNER_ID)
    result = await service.get_trip(query)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_get_trip_returns_summary_with_all_fields() -> None:
    service, repo, _ = _make_service()
    trip = await _create_and_save_trip(repo, title="Full Fields")
    query = GetTripQuery(trip_id=str(trip.trip_id), requester_id=OWNER_ID)
    result = await service.get_trip(query)
    assert isinstance(result, Success)
    s = result.value
    assert s.version >= 1
    assert s.created_at is not None
    assert s.updated_at is not None
    assert s.deleted_at is None


# ─────────────────────────────────────────────────────────────────────────────
# list_trips
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_trips_empty_for_new_user() -> None:
    service, repo, _ = _make_service()
    query = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID)
    result = await service.list_trips(query)
    assert isinstance(result, Success)
    page = result.value
    assert len(page.items) == 0
    assert page.has_more is False
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_list_trips_returns_own_trips_only() -> None:
    service, repo, _ = _make_service()
    await _create_and_save_trip(repo, owner_id=OWNER_ID, title="Mine")
    await _create_and_save_trip(repo, owner_id=OTHER_OWNER_ID, title="Theirs")
    query = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID)
    result = await service.list_trips(query)
    assert isinstance(result, Success)
    assert len(result.value.items) == 1
    assert result.value.items[0].title == "Mine"


@pytest.mark.asyncio
async def test_list_trips_excludes_deleted() -> None:
    service, repo, _ = _make_service()
    live = await _create_and_save_trip(repo, title="Live")
    deleted = await _create_and_save_trip(repo, title="Dead")
    deleted.delete()
    deleted.pop_events()
    await repo.save(deleted)
    query = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID)
    result = await service.list_trips(query)
    assert isinstance(result, Success)
    assert len(result.value.items) == 1
    assert result.value.items[0].title == "Live"


@pytest.mark.asyncio
async def test_list_trips_has_more_when_page_not_exhausted() -> None:
    service, repo, _ = _make_service()
    now = datetime.now(UTC)
    for i in range(3):
        t = await _create_and_save_trip(repo, title=f"Trip {i}")
        t.created_at = now - timedelta(minutes=i)
        await repo.save(t)
    query = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID, limit=2)
    result = await service.list_trips(query)
    assert isinstance(result, Success)
    page = result.value
    assert page.has_more is True
    assert page.next_cursor is not None
    assert len(page.items) == 2


@pytest.mark.asyncio
async def test_list_trips_cursor_returns_next_page() -> None:
    service, repo, _ = _make_service()
    now = datetime.now(UTC)
    trips = []
    for i in range(3):
        t = await _create_and_save_trip(repo, title=f"Trip {i}")
        t.created_at = now - timedelta(minutes=i)
        await repo.save(t)
        trips.append(t)

    # First page
    q1 = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID, limit=2)
    r1 = await service.list_trips(q1)
    assert isinstance(r1, Success)
    cursor = r1.value.next_cursor

    # Second page
    q2 = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID, limit=2, cursor=cursor)
    r2 = await service.list_trips(q2)
    assert isinstance(r2, Success)
    page2 = r2.value
    assert page2.has_more is False
    assert len(page2.items) == 1


@pytest.mark.asyncio
async def test_list_trips_status_filter() -> None:
    service, repo, _ = _make_service()
    draft = await _create_and_save_trip(repo, title="Draft", status=TripStatus.DRAFT)
    planned = await _create_and_save_trip(repo, title="Planned", status=TripStatus.PLANNED)
    query = ListTripsQuery(
        owner_id=OWNER_ID, requester_id=OWNER_ID, status_filter="planned"
    )
    result = await service.list_trips(query)
    assert isinstance(result, Success)
    assert len(result.value.items) == 1
    assert result.value.items[0].title == "Planned"


@pytest.mark.asyncio
async def test_list_trips_invalid_status_filter_returns_failure() -> None:
    service, _, _ = _make_service()
    query = ListTripsQuery(
        owner_id=OWNER_ID, requester_id=OWNER_ID, status_filter="not_a_status"
    )
    result = await service.list_trips(query)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValidationError)


@pytest.mark.asyncio
async def test_list_trips_forbidden_when_requester_differs() -> None:
    service, _, _ = _make_service()
    query = ListTripsQuery(owner_id=OWNER_ID, requester_id=OTHER_OWNER_ID)
    result = await service.list_trips(query)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_list_trips_invalid_cursor_returns_failure() -> None:
    service, _, _ = _make_service()
    query = ListTripsQuery(
        owner_id=OWNER_ID, requester_id=OWNER_ID, cursor="not-valid-base64!!!"
    )
    result = await service.list_trips(query)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValidationError)


@pytest.mark.asyncio
async def test_list_trips_limit_is_respected() -> None:
    service, repo, _ = _make_service()
    for i in range(5):
        await _create_and_save_trip(repo, title=f"Trip {i}")
    query = ListTripsQuery(owner_id=OWNER_ID, requester_id=OWNER_ID, limit=3)
    result = await service.list_trips(query)
    assert isinstance(result, Success)
    assert len(result.value.items) == 3
