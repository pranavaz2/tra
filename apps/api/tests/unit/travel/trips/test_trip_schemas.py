"""Unit tests for trip Pydantic schemas and RFC 7807 error responses."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.application.dtos import TripListPage, TripSummary
from app.modules.travel.trips.domain.errors import (
    InvalidTripStatusTransitionError,
    TripAlreadyDeletedError,
    TripNotFoundError,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.presentation.error_responses import map_trip_failure
from app.modules.travel.trips.presentation.schemas import (
    TripCreateRequest,
    TripPageResponse,
    TripResponse,
    TripUpdateRequest,
)
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

TRACE_ID = "test-trace-id"
INSTANCE = "/api/v1/trips"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _make_summary(
    *,
    title: str = "Test Trip",
    status: TripStatus = TripStatus.DRAFT,
    privacy: TripPrivacy = TripPrivacy.PRIVATE,
    departure_date: date | None = None,
    return_date: date | None = None,
    is_date_flexible: bool = False,
    version: int = 1,
    deleted_at: datetime | None = None,
) -> TripSummary:
    now = datetime.now(UTC)
    return TripSummary(
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=UserId.from_str(str(uuid.uuid4())),
        title=title,
        status=status,
        privacy=privacy,
        departure_date=departure_date,
        return_date=return_date,
        is_date_flexible=is_date_flexible,
        version=version,
        created_at=now,
        updated_at=now,
        deleted_at=deleted_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TripCreateRequest
# ─────────────────────────────────────────────────────────────────────────────


def test_create_request_valid_minimal() -> None:
    req = TripCreateRequest(title="Tokyo Plan")
    assert req.title == "Tokyo Plan"
    assert req.privacy is None
    assert req.departure_date is None
    assert req.return_date is None
    assert req.is_date_flexible is False


def test_create_request_strips_whitespace() -> None:
    req = TripCreateRequest(title="  Tokyo Plan  ")
    assert req.title == "Tokyo Plan"


def test_create_request_rejects_empty_title() -> None:
    with pytest.raises(PydanticValidationError):
        TripCreateRequest(title="")


def test_create_request_rejects_title_over_100_chars() -> None:
    with pytest.raises(PydanticValidationError):
        TripCreateRequest(title="X" * 101)


def test_create_request_accepts_exactly_100_char_title() -> None:
    req = TripCreateRequest(title="X" * 100)
    assert len(req.title) == 100


def test_create_request_rejects_whitespace_only_title() -> None:
    with pytest.raises(PydanticValidationError):
        TripCreateRequest(title="   ")


def test_create_request_accepts_all_optional_fields() -> None:
    req = TripCreateRequest(
        title="Trip",
        privacy="link_only",
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 7),
        is_date_flexible=True,
    )
    assert req.privacy == "link_only"
    assert req.departure_date == date(2027, 6, 1)
    assert req.return_date == date(2027, 6, 7)
    assert req.is_date_flexible is True


# ─────────────────────────────────────────────────────────────────────────────
# TripUpdateRequest
# ─────────────────────────────────────────────────────────────────────────────


def test_update_request_all_optional() -> None:
    req = TripUpdateRequest()
    assert req.title is None
    assert req.privacy is None
    assert req.new_status is None
    assert req.update_dates is False
    assert req.departure_date is None
    assert req.return_date is None
    assert req.is_date_flexible is False


def test_update_request_strips_whitespace_on_title() -> None:
    req = TripUpdateRequest(title="  New Title  ")
    assert req.title == "New Title"


def test_update_request_rejects_empty_title_when_provided() -> None:
    with pytest.raises(PydanticValidationError):
        TripUpdateRequest(title="")


def test_update_request_rejects_title_over_100_chars() -> None:
    with pytest.raises(PydanticValidationError):
        TripUpdateRequest(title="X" * 101)


def test_update_request_accepts_partial_update() -> None:
    req = TripUpdateRequest(title="New Title", new_status="planned")
    assert req.title == "New Title"
    assert req.new_status == "planned"
    assert req.privacy is None


# ─────────────────────────────────────────────────────────────────────────────
# TripResponse.from_summary
# ─────────────────────────────────────────────────────────────────────────────


def test_trip_response_from_summary_maps_all_fields() -> None:
    now = datetime.now(UTC)
    trip_id = TripId(value=uuid.uuid4())
    owner_id = UserId.from_str(str(uuid.uuid4()))
    summary = TripSummary(
        trip_id=trip_id,
        owner_id=owner_id,
        title="Mapped Trip",
        status=TripStatus.PLANNED,
        privacy=TripPrivacy.LINK_ONLY,
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 7),
        is_date_flexible=True,
        version=3,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    resp = TripResponse.from_summary(summary)
    assert resp.trip_id == str(trip_id)
    assert resp.owner_id == str(owner_id)
    assert resp.title == "Mapped Trip"
    assert resp.status == "planned"
    assert resp.privacy == "link_only"
    assert resp.departure_date == date(2027, 6, 1)
    assert resp.return_date == date(2027, 6, 7)
    assert resp.is_date_flexible is True
    assert resp.version == 3
    assert resp.created_at == now
    assert resp.updated_at == now
    assert resp.deleted_at is None


def test_trip_response_from_summary_deleted() -> None:
    deleted_at = datetime.now(UTC)
    summary = _make_summary(deleted_at=deleted_at)
    resp = TripResponse.from_summary(summary)
    assert resp.deleted_at == deleted_at


def test_trip_response_from_summary_no_dates() -> None:
    summary = _make_summary(departure_date=None, return_date=None)
    resp = TripResponse.from_summary(summary)
    assert resp.departure_date is None
    assert resp.return_date is None


# ─────────────────────────────────────────────────────────────────────────────
# TripPageResponse.from_page
# ─────────────────────────────────────────────────────────────────────────────


def test_page_response_from_empty_page() -> None:
    page = TripListPage(items=(), next_cursor=None, has_more=False, limit=20)
    resp = TripPageResponse.from_page(page)
    assert resp.items == []
    assert resp.next_cursor is None
    assert resp.has_more is False
    assert resp.limit == 20


def test_page_response_from_page_with_items() -> None:
    s1 = _make_summary(title="A")
    s2 = _make_summary(title="B")
    page = TripListPage(items=(s1, s2), next_cursor="cursor123", has_more=True, limit=2)
    resp = TripPageResponse.from_page(page)
    assert len(resp.items) == 2
    assert resp.items[0].title == "A"
    assert resp.items[1].title == "B"
    assert resp.next_cursor == "cursor123"
    assert resp.has_more is True


# ─────────────────────────────────────────────────────────────────────────────
# map_trip_failure — error response mapping
# ─────────────────────────────────────────────────────────────────────────────


def _body(response: object) -> dict:
    """Extract JSON body from a JSONResponse."""
    import json

    return json.loads(response.body)  # type: ignore[attr-defined]


def test_map_not_found_returns_404() -> None:
    err = TripNotFoundError("abc-123")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 404
    body = _body(resp)
    assert body["error_code"] == "TRIP_NOT_FOUND"
    assert body["status"] == 404


def test_map_already_deleted_returns_404() -> None:
    err = TripAlreadyDeletedError()
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 404
    body = _body(resp)
    assert body["error_code"] == "TRIP_NOT_FOUND"


def test_map_forbidden_returns_403() -> None:
    err = ForbiddenError("You do not have access.")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 403
    body = _body(resp)
    assert body["error_code"] == "TRIP_FORBIDDEN"
    assert body["status"] == 403


def test_map_invalid_status_transition_returns_422() -> None:
    err = InvalidTripStatusTransitionError(from_status="draft", to_status="completed")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 422
    body = _body(resp)
    assert body["error_code"] == "TRIP_INVALID_STATUS_TRANSITION"
    assert body["from_status"] == "draft"
    assert body["to_status"] == "completed"


def test_map_validation_error_returns_422() -> None:
    err = ValidationError("Title is too short.", field="title", value="")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 422
    body = _body(resp)
    assert body["error_code"] == "VALIDATION_ERROR"
    assert body["status"] == 422


def test_map_conflict_returns_409() -> None:
    err = ConflictError("A trip with this title already exists.")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 409
    body = _body(resp)
    assert body["error_code"] == "TRIP_CONFLICT"
    assert body["status"] == 409


def test_map_infrastructure_error_returns_503() -> None:
    err = InfrastructureError("DB failed.")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 503
    body = _body(resp)
    assert body["error_code"] == "TRIP_SERVICE_UNAVAILABLE"
    assert "temporarily unavailable" in body["detail"]


def test_map_infrastructure_error_does_not_leak_internal_message() -> None:
    err = InfrastructureError("Sensitive internal DB password error detail.")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    body = _body(resp)
    assert "Sensitive" not in body["detail"]
    assert "password" not in body["detail"]


def test_map_unknown_error_returns_500() -> None:
    class _UnknownError(TravixError):
        code = "unknown"

        def __init__(self) -> None:
            super().__init__("Some unknown domain error.")

    err = _UnknownError()
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    assert resp.status_code == 500
    body = _body(resp)
    assert body["error_code"] == "TRIP_INTERNAL_ERROR"


def test_error_response_contains_rfc7807_fields() -> None:
    err = TripNotFoundError("some-id")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    body = _body(resp)
    for field in ("type", "title", "status", "detail", "instance", "error_code", "trace_id"):
        assert field in body, f"Missing RFC 7807 field: {field}"


def test_error_response_sets_trace_id() -> None:
    err = ForbiddenError("Denied.")
    resp = map_trip_failure(err, trace_id="my-trace-abc", instance=INSTANCE)
    body = _body(resp)
    assert body["trace_id"] == "my-trace-abc"


def test_error_response_sets_instance() -> None:
    err = TripNotFoundError("x")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance="/api/v1/trips/x")
    body = _body(resp)
    assert body["instance"] == "/api/v1/trips/x"


def test_error_type_uri_has_trips_prefix() -> None:
    err = TripNotFoundError("x")
    resp = map_trip_failure(err, trace_id=TRACE_ID, instance=INSTANCE)
    body = _body(resp)
    assert body["type"].startswith("https://errors.travix.ai/trips")
