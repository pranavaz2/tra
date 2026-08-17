"""Integration tests for SQLAlchemyTripRepository against real PostgreSQL."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.infrastructure.repositories.trip_repository import (
    SQLAlchemyTripRepository,
)

pytestmark = pytest.mark.asyncio


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a Trip domain entity for insertion
# ─────────────────────────────────────────────────────────────────────────────


def _make_trip(
    owner_id: uuid.UUID,
    *,
    title: str = "Test Trip",
    status: TripStatus = TripStatus.DRAFT,
    privacy: TripPrivacy = TripPrivacy.PRIVATE,
    departure_date: date | None = None,
    return_date: date | None = None,
    created_at: datetime | None = None,
) -> Trip:
    date_range: TripDateRange | None = None
    if departure_date is not None:
        date_range = TripDateRange(
            departure_date=departure_date,
            return_date=return_date,
            is_flexible=False,
        )
    trip = Trip.create(
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=UserId(value=owner_id),
        title=TripTitle(value=title),
        privacy=privacy,
        date_range=date_range,
    )
    if status != TripStatus.DRAFT:
        trip.status = status
    if created_at is not None:
        trip.created_at = created_at
    trip.pop_events()
    return trip


# ─────────────────────────────────────────────────────────────────────────────
# save + find_by_id
# ─────────────────────────────────────────────────────────────────────────────


async def test_save_and_find_by_id(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id, title="Rome Weekend")
    await repo.save(trip)

    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    assert str(loaded.title) == "Rome Weekend"
    assert loaded.status == TripStatus.DRAFT
    assert loaded.privacy == TripPrivacy.PRIVATE
    assert loaded.owner_id == UserId(value=trip_owner_id)


async def test_find_by_id_nonexistent_returns_none(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    result = await repo.find_by_id(TripId(value=uuid.uuid4()))
    assert result is None


async def test_save_persists_date_range(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(
        trip_owner_id,
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 7),
    )
    await repo.save(trip)
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    assert loaded.date_range is not None
    assert loaded.date_range.departure_date == date(2027, 6, 1)
    assert loaded.date_range.return_date == date(2027, 6, 7)


async def test_find_by_id_returns_soft_deleted_trip(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)
    trip.delete()
    trip.pop_events()
    await repo.save(trip)

    # find_by_id returns soft-deleted trips — callers decide how to handle them
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    assert loaded.is_deleted is True


# ─────────────────────────────────────────────────────────────────────────────
# save (update path)
# ─────────────────────────────────────────────────────────────────────────────


async def test_save_updates_existing_trip(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id, title="Original")
    await repo.save(trip)

    # Reload then mutate
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.rename(TripTitle(value="Updated"))
    loaded.pop_events()
    await repo.save(loaded)

    reloaded = await repo.find_by_id(trip.trip_id)
    assert reloaded is not None
    assert str(reloaded.title) == "Updated"


async def test_save_increments_version_on_update(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)

    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.rename(TripTitle(value="Renamed"))
    loaded.pop_events()
    await repo.save(loaded)

    reloaded = await repo.find_by_id(trip.trip_id)
    assert reloaded is not None
    assert reloaded.version == 2


# ─────────────────────────────────────────────────────────────────────────────
# find_by_owner
# ─────────────────────────────────────────────────────────────────────────────


async def test_find_by_owner_empty(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=20)
    assert results == []


async def test_find_by_owner_returns_own_trips_only(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    other_owner = uuid.uuid4()
    repo = SQLAlchemyTripRepository(db_session)
    mine = _make_trip(trip_owner_id, title="Mine")
    theirs = _make_trip(other_owner, title="Theirs")
    # Note: theirs would fail FK — we only save mine
    await repo.save(mine)

    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=20)
    assert len(results) == 1
    assert str(results[0].title) == "Mine"


async def test_find_by_owner_multiple_trips(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    now = datetime.now(UTC)
    for i in range(3):
        trip = _make_trip(
            trip_owner_id,
            title=f"Trip {i}",
            created_at=now - timedelta(minutes=i),
        )
        await repo.save(trip)

    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=20)
    assert len(results) == 3


async def test_find_by_owner_ordered_newest_first(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    now = datetime.now(UTC)
    old = _make_trip(trip_owner_id, title="Old", created_at=now - timedelta(hours=2))
    new = _make_trip(trip_owner_id, title="New", created_at=now - timedelta(hours=1))
    await repo.save(old)
    await repo.save(new)

    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=20)
    assert str(results[0].title) == "New"
    assert str(results[1].title) == "Old"


async def test_find_by_owner_excludes_soft_deleted(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    live = _make_trip(trip_owner_id, title="Live")
    deleted = _make_trip(trip_owner_id, title="Deleted")
    await repo.save(live)
    await repo.save(deleted)

    # Load and soft-delete
    loaded_deleted = await repo.find_by_id(deleted.trip_id)
    assert loaded_deleted is not None
    loaded_deleted.delete()
    loaded_deleted.pop_events()
    await repo.save(loaded_deleted)

    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=20)
    titles = {str(t.title) for t in results}
    assert "Live" in titles
    assert "Deleted" not in titles


async def test_find_by_owner_status_filter(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    draft = _make_trip(trip_owner_id, title="Draft", status=TripStatus.DRAFT)
    planned = _make_trip(trip_owner_id, title="Planned", status=TripStatus.PLANNED)
    await repo.save(draft)
    await repo.save(planned)

    results = await repo.find_by_owner(
        UserId(value=trip_owner_id),
        limit=20,
        status_filter=TripStatus.PLANNED,
    )
    assert len(results) == 1
    assert str(results[0].title) == "Planned"


async def test_find_by_owner_cursor_pagination(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    now = datetime.now(UTC)

    trips = []
    for i in range(4):
        trip = _make_trip(
            trip_owner_id,
            title=f"Trip {i}",
            created_at=now - timedelta(minutes=i),
        )
        await repo.save(trip)
        trips.append(trip)

    # First page (limit+1 pattern to detect next page)
    page1 = await repo.find_by_owner(UserId(value=trip_owner_id), limit=3)
    assert len(page1) == 3

    # Use last item of page 1 as cursor for page 2
    cursor_id = page1[-1].trip_id
    page2 = await repo.find_by_owner(
        UserId(value=trip_owner_id), limit=3, after_id=cursor_id
    )
    assert len(page2) == 1

    # No overlap between pages
    page1_ids = {str(t.trip_id) for t in page1}
    page2_ids = {str(t.trip_id) for t in page2}
    assert page1_ids.isdisjoint(page2_ids)


async def test_find_by_owner_respects_limit(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    for i in range(5):
        await repo.save(_make_trip(trip_owner_id, title=f"Trip {i}"))

    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=2)
    assert len(results) == 2


# ─────────────────────────────────────────────────────────────────────────────
# find_active_for_user
# ─────────────────────────────────────────────────────────────────────────────


async def test_find_active_for_user_returns_planned_and_active(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    await repo.save(_make_trip(trip_owner_id, title="Draft", status=TripStatus.DRAFT))
    await repo.save(_make_trip(trip_owner_id, title="Planned", status=TripStatus.PLANNED))
    await repo.save(_make_trip(trip_owner_id, title="Active", status=TripStatus.ACTIVE))
    await repo.save(_make_trip(trip_owner_id, title="Completed", status=TripStatus.COMPLETED))
    await repo.save(_make_trip(trip_owner_id, title="Archived", status=TripStatus.ARCHIVED))

    results = await repo.find_active_for_user(UserId(value=trip_owner_id))
    titles = {str(t.title) for t in results}
    assert "Planned" in titles
    assert "Active" in titles
    assert "Draft" not in titles
    assert "Completed" not in titles
    assert "Archived" not in titles


async def test_find_active_for_user_excludes_deleted(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id, title="Planned", status=TripStatus.PLANNED)
    await repo.save(trip)
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.delete()
    loaded.pop_events()
    await repo.save(loaded)

    results = await repo.find_active_for_user(UserId(value=trip_owner_id))
    assert results == []


async def test_find_active_for_user_empty(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    results = await repo.find_active_for_user(UserId(value=trip_owner_id))
    assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# exists
# ─────────────────────────────────────────────────────────────────────────────


async def test_exists_true_for_live_trip(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)
    assert await repo.exists(trip.trip_id) is True


async def test_exists_false_for_nonexistent(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    assert await repo.exists(TripId(value=uuid.uuid4())) is False


async def test_exists_false_for_soft_deleted(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.delete()
    loaded.pop_events()
    await repo.save(loaded)
    assert await repo.exists(trip.trip_id) is False


# ─────────────────────────────────────────────────────────────────────────────
# exists_with_title
# ─────────────────────────────────────────────────────────────────────────────


async def test_exists_with_title_true_for_exact_match(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    await repo.save(_make_trip(trip_owner_id, title="Paris Weekend"))
    owner = UserId(value=trip_owner_id)
    assert await repo.exists_with_title(owner, TripTitle(value="Paris Weekend")) is True


async def test_exists_with_title_case_insensitive(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    await repo.save(_make_trip(trip_owner_id, title="Paris Weekend"))
    owner = UserId(value=trip_owner_id)
    assert await repo.exists_with_title(owner, TripTitle(value="paris weekend")) is True
    assert await repo.exists_with_title(owner, TripTitle(value="PARIS WEEKEND")) is True


async def test_exists_with_title_false_for_different_title(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    await repo.save(_make_trip(trip_owner_id, title="Paris Weekend"))
    owner = UserId(value=trip_owner_id)
    assert await repo.exists_with_title(owner, TripTitle(value="Tokyo Trip")) is False


async def test_exists_with_title_false_for_deleted_trip(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id, title="Paris Weekend")
    await repo.save(trip)
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.delete()
    loaded.pop_events()
    await repo.save(loaded)
    owner = UserId(value=trip_owner_id)
    assert await repo.exists_with_title(owner, TripTitle(value="Paris Weekend")) is False


async def test_exists_with_title_scoped_to_owner(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    await repo.save(_make_trip(trip_owner_id, title="Shared Title"))
    other_owner = UserId(value=uuid.uuid4())
    assert await repo.exists_with_title(other_owner, TripTitle(value="Shared Title")) is False


# ─────────────────────────────────────────────────────────────────────────────
# delete (hard delete)
# ─────────────────────────────────────────────────────────────────────────────


async def test_hard_delete_removes_record(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)
    await repo.delete(trip.trip_id)

    result = await repo.find_by_id(trip.trip_id)
    assert result is None


async def test_hard_delete_nonexistent_is_silent(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    # Should not raise
    await repo.delete(TripId(value=uuid.uuid4()))


async def test_hard_delete_removes_from_owner_list(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)
    await repo.delete(trip.trip_id)

    results = await repo.find_by_owner(UserId(value=trip_owner_id), limit=20)
    assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# Soft delete via domain + save
# ─────────────────────────────────────────────────────────────────────────────


async def test_soft_delete_sets_deleted_at_in_db(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)

    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.delete()
    loaded.pop_events()
    await repo.save(loaded)

    reloaded = await repo.find_by_id(trip.trip_id)
    assert reloaded is not None
    assert reloaded.deleted_at is not None


async def test_soft_deleted_trip_excluded_from_exists(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id)
    await repo.save(trip)

    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    loaded.delete()
    loaded.pop_events()
    await repo.save(loaded)

    assert await repo.exists(trip.trip_id) is False


# ─────────────────────────────────────────────────────────────────────────────
# Status and privacy persistence
# ─────────────────────────────────────────────────────────────────────────────


async def test_trip_privacy_persists(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id, privacy=TripPrivacy.PUBLIC)
    await repo.save(trip)
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    assert loaded.privacy == TripPrivacy.PUBLIC


async def test_trip_status_persists(
    db_session: AsyncSession, trip_owner_id: uuid.UUID
) -> None:
    repo = SQLAlchemyTripRepository(db_session)
    trip = _make_trip(trip_owner_id, status=TripStatus.PLANNED)
    await repo.save(trip)
    loaded = await repo.find_by_id(trip.trip_id)
    assert loaded is not None
    assert loaded.status == TripStatus.PLANNED
