"""
Trip application DTOs.

Data Transfer Objects returned by TripService use cases. These are
application-layer types — they are NOT Pydantic schemas and are NOT
serialised directly into HTTP responses. The presentation layer
(router + schemas) converts them into Pydantic response models.

DTOs use domain value objects (TripId, UserId, TripStatus, TripPrivacy)
for type safety. The presentation layer unpacks them into serialisable
primitives (str, dict, etc.) before building HTTP responses.

Naming convention (per CLAUDE.md §8):
  TripSummary    — result of a single-trip read or write operation.
  TripListPage   — result of a paginated list operation.

Result type aliases:
  These aliases give a precise name to the Result[T] specialisation for
  each use case. Handlers and routes import the alias rather than
  repeating the generic signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.shared.domain.result import Result


@dataclass(frozen=True)
class TripSummary:
    """
    Snapshot of a Trip aggregate's current state.

    Returned by create, update, get, and — for each item — list operations.
    Contains all fields needed for both list cards and detail screens.

    Fields use domain value objects where they carry semantic type information
    (TripId, UserId, TripStatus, TripPrivacy). Scalar leaf values (title,
    dates, booleans, timestamps) are plain Python types.

    Attributes:
        trip_id:         The trip's unique identity.
        owner_id:        The owning user's identity.
        title:           Stripped trip name (always 1–100 characters).
        status:          Current lifecycle status.
        privacy:         Current visibility setting.
        departure_date:  First day of the trip, or None if not scheduled.
        return_date:     Last day of the trip, or None if open-ended or
                         not yet scheduled.
        is_date_flexible: True when the user has not committed to exact dates.
        version:         Optimistic concurrency version counter. The presentation
                         layer may pass this back for optimistic-lock conflict
                         detection on update.
        created_at:      UTC timestamp of trip creation.
        updated_at:      UTC timestamp of the last mutation.
        deleted_at:      UTC timestamp of soft deletion, or None if live.
    """

    trip_id: TripId
    owner_id: UserId
    title: str
    status: TripStatus
    privacy: TripPrivacy
    departure_date: date | None
    return_date: date | None
    is_date_flexible: bool
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True)
class TripListPage:
    """
    A single page of paginated trip results.

    Returned by ListTripsQuery. The presentation layer converts items to
    Pydantic schemas and forwards next_cursor as an opaque token to the client.

    Cursor semantics:
      - next_cursor is a base64url-encoded TripId string. It is opaque to
        clients — they must not parse or construct it.
      - When next_cursor is None, this is the last page.
      - Pass next_cursor as the cursor field of the next ListTripsQuery to
        retrieve the following page.

    Attributes:
        items:       Ordered list of trip summaries for this page, newest-first.
                     Length is at most `limit`.
        next_cursor: Encoded cursor for the next page, or None if last page.
        has_more:    True if at least one more page follows this one.
        limit:       The page size that was applied (after clamping).
    """

    items: tuple[TripSummary, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


# ---------------------------------------------------------------------------
# Result type aliases — one per use case
# ---------------------------------------------------------------------------

from typing import TypeAlias

CreateTripResult: TypeAlias = "Result[TripSummary]"
UpdateTripResult: TypeAlias = "Result[TripSummary]"
DeleteTripResult: TypeAlias = "Result[None]"
GetTripResult: TypeAlias = "Result[TripSummary]"
ListTripsResult: TypeAlias = "Result[TripListPage]"
