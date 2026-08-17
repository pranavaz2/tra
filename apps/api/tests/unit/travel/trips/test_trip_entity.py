"""Unit tests for the Trip domain aggregate."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.entities.trip import Trip
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
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_trip(
    *,
    title: str = "Paris Weekend",
    privacy: TripPrivacy = TripPrivacy.PRIVATE,
    date_range: TripDateRange | None = None,
) -> Trip:
    return Trip.create(
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=UserId.from_str(str(uuid.uuid4())),
        title=TripTitle(value=title),
        privacy=privacy,
        date_range=date_range,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trip.create
# ─────────────────────────────────────────────────────────────────────────────


def test_create_sets_draft_status() -> None:
    trip = _make_trip()
    assert trip.status == TripStatus.DRAFT


def test_create_sets_provided_title() -> None:
    trip = _make_trip(title="Rome Trip")
    assert str(trip.title) == "Rome Trip"


def test_create_sets_version_to_one() -> None:
    trip = _make_trip()
    assert trip.version == 1


def test_create_not_deleted() -> None:
    trip = _make_trip()
    assert trip.is_deleted is False
    assert trip.deleted_at is None


def test_create_emits_trip_created_event() -> None:
    trip = _make_trip()
    events = trip.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripCreated)


def test_create_event_carries_title() -> None:
    trip = _make_trip(title="Tokyo Plan")
    event = trip.pop_events()[0]
    assert isinstance(event, TripCreated)
    assert event.title == "Tokyo Plan"


def test_create_event_carries_status_draft() -> None:
    trip = _make_trip()
    event = trip.pop_events()[0]
    assert isinstance(event, TripCreated)
    assert event.status == "draft"


def test_create_event_carries_privacy() -> None:
    trip = _make_trip(privacy=TripPrivacy.PUBLIC)
    event = trip.pop_events()[0]
    assert isinstance(event, TripCreated)
    assert event.privacy == "public"


def test_create_event_carries_date_range() -> None:
    dr = TripDateRange(
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 7),
        is_flexible=False,
    )
    trip = _make_trip(date_range=dr)
    event = trip.pop_events()[0]
    assert isinstance(event, TripCreated)
    assert event.departure_date == date(2027, 6, 1)
    assert event.return_date == date(2027, 6, 7)


def test_create_event_no_dates_when_unscheduled() -> None:
    trip = _make_trip()
    event = trip.pop_events()[0]
    assert isinstance(event, TripCreated)
    assert event.departure_date is None
    assert event.return_date is None


# ─────────────────────────────────────────────────────────────────────────────
# pop_events clears the buffer
# ─────────────────────────────────────────────────────────────────────────────


def test_pop_events_clears_pending() -> None:
    trip = _make_trip()
    trip.pop_events()  # consume TripCreated
    assert trip.pop_events() == []


def test_pop_events_returns_in_order() -> None:
    trip = _make_trip()
    trip.pop_events()  # clear TripCreated
    trip.rename(TripTitle(value="A"))
    trip.rename(TripTitle(value="B"))
    events = trip.pop_events()
    assert len(events) == 2
    assert isinstance(events[0], TripUpdated)
    assert isinstance(events[1], TripUpdated)


# ─────────────────────────────────────────────────────────────────────────────
# rename
# ─────────────────────────────────────────────────────────────────────────────


def test_rename_updates_title() -> None:
    trip = _make_trip(title="Old Title")
    trip.rename(TripTitle(value="New Title"))
    assert str(trip.title) == "New Title"


def test_rename_increments_version() -> None:
    trip = _make_trip()
    trip.rename(TripTitle(value="New Title"))
    assert trip.version == 2


def test_rename_emits_trip_updated() -> None:
    trip = _make_trip()
    trip.pop_events()
    trip.rename(TripTitle(value="New Title"))
    events = trip.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripUpdated)
    assert "title" in events[0].changed_fields


def test_rename_raises_if_deleted() -> None:
    trip = _make_trip()
    trip.delete()
    with pytest.raises(TripAlreadyDeletedError):
        trip.rename(TripTitle(value="Anything"))


# ─────────────────────────────────────────────────────────────────────────────
# reschedule
# ─────────────────────────────────────────────────────────────────────────────


def test_reschedule_sets_date_range() -> None:
    trip = _make_trip()
    dr = TripDateRange(
        departure_date=date(2027, 8, 1),
        return_date=date(2027, 8, 10),
        is_flexible=True,
    )
    trip.reschedule(dr)
    assert trip.date_range is not None
    assert trip.date_range.departure_date == date(2027, 8, 1)


def test_reschedule_clears_date_range_when_none() -> None:
    dr = TripDateRange(
        departure_date=date(2027, 8, 1), return_date=None, is_flexible=False
    )
    trip = _make_trip(date_range=dr)
    trip.reschedule(None)
    assert trip.date_range is None


def test_reschedule_emits_trip_updated() -> None:
    trip = _make_trip()
    trip.pop_events()
    trip.reschedule(None)
    events = trip.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripUpdated)
    assert "date_range" in events[0].changed_fields


def test_reschedule_raises_if_deleted() -> None:
    trip = _make_trip()
    trip.delete()
    with pytest.raises(TripAlreadyDeletedError):
        trip.reschedule(None)


# ─────────────────────────────────────────────────────────────────────────────
# change_privacy
# ─────────────────────────────────────────────────────────────────────────────


def test_change_privacy_updates_value() -> None:
    trip = _make_trip(privacy=TripPrivacy.PRIVATE)
    trip.change_privacy(TripPrivacy.PUBLIC)
    assert trip.privacy == TripPrivacy.PUBLIC


def test_change_privacy_increments_version() -> None:
    trip = _make_trip()
    trip.change_privacy(TripPrivacy.LINK_ONLY)
    assert trip.version == 2


def test_change_privacy_emits_trip_updated() -> None:
    trip = _make_trip()
    trip.pop_events()
    trip.change_privacy(TripPrivacy.LINK_ONLY)
    events = trip.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripUpdated)
    assert "privacy" in events[0].changed_fields


def test_change_privacy_raises_if_deleted() -> None:
    trip = _make_trip()
    trip.delete()
    with pytest.raises(TripAlreadyDeletedError):
        trip.change_privacy(TripPrivacy.PUBLIC)


# ─────────────────────────────────────────────────────────────────────────────
# transition_to — valid transitions
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "from_status, to_status",
    [
        (TripStatus.DRAFT, TripStatus.PLANNED),
        (TripStatus.DRAFT, TripStatus.ARCHIVED),
        (TripStatus.PLANNED, TripStatus.ACTIVE),
        (TripStatus.PLANNED, TripStatus.DRAFT),
        (TripStatus.PLANNED, TripStatus.ARCHIVED),
        (TripStatus.ACTIVE, TripStatus.COMPLETED),
        (TripStatus.ACTIVE, TripStatus.ARCHIVED),
        (TripStatus.COMPLETED, TripStatus.ARCHIVED),
    ],
)
def test_valid_status_transition(from_status: TripStatus, to_status: TripStatus) -> None:
    trip = _make_trip()
    trip.pop_events()
    # Manually set the status to the desired starting point.
    object.__setattr__(trip, "status", from_status)
    trip.transition_to(to_status)
    assert trip.status == to_status


def test_transition_to_increments_version() -> None:
    trip = _make_trip()
    trip.transition_to(TripStatus.PLANNED)
    assert trip.version == 2


def test_transition_to_emits_status_changed() -> None:
    trip = _make_trip()
    trip.pop_events()
    trip.transition_to(TripStatus.PLANNED)
    events = trip.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripStatusChanged)
    assert events[0].old_status == "draft"
    assert events[0].new_status == "planned"


# ─────────────────────────────────────────────────────────────────────────────
# transition_to — invalid transitions
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "from_status, to_status",
    [
        (TripStatus.DRAFT, TripStatus.ACTIVE),
        (TripStatus.DRAFT, TripStatus.COMPLETED),
        (TripStatus.ACTIVE, TripStatus.PLANNED),
        (TripStatus.COMPLETED, TripStatus.ACTIVE),
        (TripStatus.ARCHIVED, TripStatus.DRAFT),
        (TripStatus.ARCHIVED, TripStatus.PLANNED),
        (TripStatus.ARCHIVED, TripStatus.ACTIVE),
        (TripStatus.ARCHIVED, TripStatus.COMPLETED),
    ],
)
def test_invalid_status_transition_raises(
    from_status: TripStatus, to_status: TripStatus
) -> None:
    trip = _make_trip()
    object.__setattr__(trip, "status", from_status)
    with pytest.raises(InvalidTripStatusTransitionError) as exc_info:
        trip.transition_to(to_status)
    assert exc_info.value.from_status == from_status.value
    assert exc_info.value.to_status == to_status.value


def test_transition_raises_if_deleted() -> None:
    trip = _make_trip()
    trip.delete()
    with pytest.raises(TripAlreadyDeletedError):
        trip.transition_to(TripStatus.PLANNED)


# ─────────────────────────────────────────────────────────────────────────────
# delete
# ─────────────────────────────────────────────────────────────────────────────


def test_delete_sets_deleted_at() -> None:
    before = datetime.now(UTC) - timedelta(seconds=1)
    trip = _make_trip()
    trip.delete()
    assert trip.deleted_at is not None
    assert trip.deleted_at >= before


def test_delete_marks_is_deleted_true() -> None:
    trip = _make_trip()
    trip.delete()
    assert trip.is_deleted is True


def test_delete_increments_version() -> None:
    trip = _make_trip()
    trip.delete()
    assert trip.version == 2


def test_delete_emits_trip_deleted_event() -> None:
    trip = _make_trip()
    trip.pop_events()
    trip.delete()
    events = trip.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripDeleted)


def test_delete_twice_raises() -> None:
    trip = _make_trip()
    trip.delete()
    with pytest.raises(TripAlreadyDeletedError):
        trip.delete()


def test_delete_event_carries_owner_id() -> None:
    owner = UserId.from_str(str(uuid.uuid4()))
    trip = Trip.create(
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=owner,
        title=TripTitle(value="X"),
    )
    trip.pop_events()
    trip.delete()
    event = trip.pop_events()[0]
    assert isinstance(event, TripDeleted)
    assert event.owner_id == str(owner)


# ─────────────────────────────────────────────────────────────────────────────
# trip_id property
# ─────────────────────────────────────────────────────────────────────────────


def test_trip_id_alias_for_entity_id() -> None:
    trip_id = TripId(value=uuid.uuid4())
    trip = Trip.create(
        trip_id=trip_id,
        owner_id=UserId.from_str(str(uuid.uuid4())),
        title=TripTitle(value="Alias Test"),
    )
    assert trip.trip_id == trip_id
    assert trip.trip_id is trip.entity_id
