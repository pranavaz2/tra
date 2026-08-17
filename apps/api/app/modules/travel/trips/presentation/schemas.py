"""
Pydantic v2 schemas for the Trips presentation layer.

These schemas perform TRANSPORT-LEVEL validation only:
  - Type coercion and whitespace stripping
  - Field presence and maximum/minimum length caps
  - No date cross-field logic (departure before return, etc.) — that belongs
    to the domain layer via TripDateRange

They do NOT perform BUSINESS validation:
  - Title uniqueness per owner → ConflictError (application layer)
  - Date ordering → TripDateRange value object (domain layer)
  - Status transition legality → Trip.update_status() (domain layer)

Schema → OpenAPI mapping:
  All schemas generate OpenAPI documentation via FastAPI. Field descriptions
  and examples feed directly into Swagger UI and ReDoc.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.modules.travel.trips.application.dtos import TripListPage, TripSummary

T = TypeVar("T")


# ──────────────────────────────────────────────────────────────────────────── #
# Generic response envelope                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


class DataEnvelope(BaseModel, Generic[T]):
    """
    Standard single-resource success envelope.

    All success responses from the Trips API are wrapped in::

        { "data": <payload> }
    """

    model_config = ConfigDict(populate_by_name=True)

    data: T


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips — Request schema                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


class TripCreateRequest(BaseModel):
    """
    POST /api/v1/trips request body.

    Transport-level validation enforced here:
      - title: non-empty, max 100 characters, whitespace stripped.
      - privacy: optional; one of "private", "link_only", "public". Defaults
        to "private" when absent (enforced in the command, not here).
      - dates: optional; only presence and type are checked. Date ordering
        is enforced by the domain's TripDateRange value object.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=100,
            description=(
                "Human-readable trip name. Stripped of leading/trailing whitespace. "
                "Must be 1–100 characters after stripping."
            ),
            examples=["Weekend in Lisbon"],
        ),
    ]

    privacy: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                'Visibility setting. One of: "private", "link_only", "public". '
                'Defaults to "private" when not provided.'
            ),
            examples=["private"],
        ),
    ] = None

    departure_date: Annotated[
        date | None,
        Field(
            default=None,
            description="First day of the trip. ISO 8601 date (YYYY-MM-DD).",
            examples=["2027-06-01"],
        ),
    ] = None

    return_date: Annotated[
        date | None,
        Field(
            default=None,
            description=(
                "Last day of the trip. ISO 8601 date (YYYY-MM-DD). "
                "Requires departure_date to be set. Must not precede departure_date."
            ),
            examples=["2027-06-07"],
        ),
    ] = None

    is_date_flexible: Annotated[
        bool,
        Field(
            default=False,
            description="True when the user has not committed to exact dates.",
        ),
    ] = False


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id} — Request schema                                        #
# ──────────────────────────────────────────────────────────────────────────── #


class TripUpdateRequest(BaseModel):
    """
    PATCH /api/v1/trips/{trip_id} request body.

    All fields are optional. Only fields that are explicitly provided
    are applied. The update_dates flag controls whether date fields are
    touched:

        update_dates=false (or absent) → date range unchanged.
        update_dates=true, departure_date=null → date range cleared.
        update_dates=true, departure_date=<date> → date range replaced.

    Transport-level validation enforced here:
      - title: when provided, 1–100 characters after stripping.
      - All other fields: type only. Business validation in application layer.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: Annotated[
        str | None,
        Field(
            default=None,
            min_length=1,
            max_length=100,
            description=(
                "New trip name. Stripped of leading/trailing whitespace. "
                "Omit to leave the title unchanged."
            ),
            examples=["Long Weekend in Porto"],
        ),
    ] = None

    privacy: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                'New visibility setting. One of: "private", "link_only", "public". '
                "Omit to leave the setting unchanged."
            ),
            examples=["link_only"],
        ),
    ] = None

    new_status: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Target lifecycle status. Must be a valid TripStatus value and a "
                "permitted transition from the current status. "
                'One of: "draft", "planned", "active", "completed", "archived". '
                "Omit to leave the status unchanged."
            ),
            examples=["planned"],
        ),
    ] = None

    update_dates: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "When true, apply the departure_date / return_date / is_date_flexible "
                "fields. When false (default), date fields are ignored and the current "
                "date range is unchanged."
            ),
        ),
    ] = False

    departure_date: Annotated[
        date | None,
        Field(
            default=None,
            description=(
                "New departure date. Only read when update_dates=true. "
                "Set to null with update_dates=true to clear the date range."
            ),
            examples=["2027-06-10"],
        ),
    ] = None

    return_date: Annotated[
        date | None,
        Field(
            default=None,
            description=(
                "New return date. Only read when update_dates=true. "
                "Requires departure_date to be set and must not precede it."
            ),
            examples=["2027-06-15"],
        ),
    ] = None

    is_date_flexible: Annotated[
        bool,
        Field(
            default=False,
            description="New flexibility flag. Only read when update_dates=true.",
        ),
    ] = False


# ──────────────────────────────────────────────────────────────────────────── #
# Trip response schemas                                                          #
# ──────────────────────────────────────────────────────────────────────────── #


class TripResponse(BaseModel):
    """
    Single-trip response body (the 'data' field).

    Returned by create, get, and update operations. Contains the full
    current state of the trip aggregate.

    Client integration:
      - Use trip_id as the stable identity for navigation and caching.
      - The version field is the optimistic-lock counter. Pass it back in
        future PATCH requests if conflict detection is needed.
      - Persist next_cursor from list responses — it is opaque and must
        not be parsed or constructed by the client.
    """

    model_config = ConfigDict(populate_by_name=True)

    trip_id: Annotated[
        str,
        Field(description="Stable UUID identifying this trip."),
    ]

    owner_id: Annotated[
        str,
        Field(description="UUID of the user who owns this trip."),
    ]

    title: Annotated[
        str,
        Field(description="Human-readable trip name."),
    ]

    status: Annotated[
        str,
        Field(
            description=(
                'Current lifecycle status. '
                'One of: "draft", "planned", "active", "completed", "archived".'
            ),
        ),
    ]

    privacy: Annotated[
        str,
        Field(
            description=(
                'Current visibility setting. '
                'One of: "private", "link_only", "public".'
            ),
        ),
    ]

    departure_date: Annotated[
        date | None,
        Field(description="First day of the trip, or null if not yet scheduled."),
    ]

    return_date: Annotated[
        date | None,
        Field(description="Last day of the trip, or null if open-ended or not scheduled."),
    ]

    is_date_flexible: Annotated[
        bool,
        Field(description="True when the user has not committed to exact dates."),
    ]

    version: Annotated[
        int,
        Field(
            description=(
                "Optimistic concurrency version counter. "
                "Incremented by the server on every successful update."
            ),
        ),
    ]

    created_at: Annotated[
        datetime,
        Field(description="ISO 8601 UTC timestamp when the trip was created."),
    ]

    updated_at: Annotated[
        datetime,
        Field(description="ISO 8601 UTC timestamp of the last mutation."),
    ]

    deleted_at: Annotated[
        datetime | None,
        Field(description="ISO 8601 UTC timestamp of soft deletion, or null if the trip is live."),
    ]

    @classmethod
    def from_summary(cls, summary: TripSummary) -> "TripResponse":
        """Convert a TripSummary application DTO to a TripResponse schema."""
        return cls(
            trip_id=str(summary.trip_id),
            owner_id=str(summary.owner_id),
            title=summary.title,
            status=summary.status.value,
            privacy=summary.privacy.value,
            departure_date=summary.departure_date,
            return_date=summary.return_date,
            is_date_flexible=summary.is_date_flexible,
            version=summary.version,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
            deleted_at=summary.deleted_at,
        )


# ──────────────────────────────────────────────────────────────────────────── #
# Paginated list response schema                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


class TripPageResponse(BaseModel):
    """
    GET /api/v1/trips response body (the 'data' field).

    Cursor-based paginated list of the authenticated user's trips.
    Results are ordered newest-first (created_at DESC).

    Cursor semantics:
      - next_cursor is an opaque token returned by the server.
        Clients must not parse, construct, or modify it.
      - Pass next_cursor as the 'cursor' query parameter to retrieve
        the following page.
      - When next_cursor is null, this is the last page.
    """

    model_config = ConfigDict(populate_by_name=True)

    items: Annotated[
        list[TripResponse],
        Field(description="Ordered list of trips for this page. Newest-first."),
    ]

    next_cursor: Annotated[
        str | None,
        Field(
            description=(
                "Opaque cursor token for the next page. "
                "Null when this is the last page."
            ),
        ),
    ]

    has_more: Annotated[
        bool,
        Field(description="True if at least one more page follows this one."),
    ]

    limit: Annotated[
        int,
        Field(description="The page size that was applied (after clamping to 1–100)."),
    ]

    @classmethod
    def from_page(cls, page: TripListPage) -> "TripPageResponse":
        """Convert a TripListPage application DTO to a TripPageResponse schema."""
        return cls(
            items=[TripResponse.from_summary(s) for s in page.items],
            next_cursor=page.next_cursor,
            has_more=page.has_more,
            limit=page.limit,
        )

