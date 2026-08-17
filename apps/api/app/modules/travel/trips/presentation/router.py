"""
Trips Presentation Layer — FastAPI Router.

Implements:
  POST   /api/v1/trips              — Create a new trip
  GET    /api/v1/trips              — List trips for the authenticated user
  GET    /api/v1/trips/{trip_id}    — Get a single trip by ID
  PATCH  /api/v1/trips/{trip_id}    — Update mutable trip fields
  DELETE /api/v1/trips/{trip_id}    — Soft-delete a trip

Responsibility (per endpoint):
  1. Receive the validated Pydantic request body / query parameters.
  2. Verify the authenticated user via RequireAuthentication.
  3. Build the appropriate command or query and call the handler.
  4. Map the Result[T] to a JSON HTTP response.
  5. Return the response with the X-Request-ID header.

What this router does NOT do:
  - Business validation (no date ordering, no title uniqueness)
  - Persistence (no direct repository access)
  - Infrastructure logic (no DB session, no Redis)
  - Raising HTTPException (all error paths build JSONResponse via error_responses)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.trips.application.commands import (
    CreateTripCommand,
    DeleteTripCommand,
    UpdateTripCommand,
)
from app.modules.travel.trips.application.queries import GetTripQuery, ListTripsQuery
from app.modules.travel.trips.infrastructure.dependencies import (
    CurrentCreateTripHandler,
    CurrentDeleteTripHandler,
    CurrentGetTripHandler,
    CurrentListTripsHandler,
    CurrentUpdateTripHandler,
)
from app.modules.travel.trips.presentation.error_responses import map_trip_failure
from app.modules.travel.trips.presentation.schemas import (
    DataEnvelope,
    TripCreateRequest,
    TripPageResponse,
    TripResponse,
    TripUpdateRequest,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Trips"])

_TRIPS_BASE = "/api/v1/trips"


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips — Create a trip                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "",
    status_code=201,
    summary="Create a new trip",
    operation_id="createTrip",
    response_description="Trip created successfully.",
    description="""
Create a new trip for the authenticated user.

The trip is created in **draft** status with **private** visibility by default.
Both the status and privacy can be changed via `PATCH /trips/{trip_id}`.

## Date range

Dates are optional. When provided:
- `departure_date` is required if `return_date` is set.
- `return_date` must not precede `departure_date`.
- Set `is_date_flexible: true` when the user has not committed to exact dates.

## Error codes

| HTTP | error_code | Cause |
|------|-----------|-------|
| 409  | TRIP_CONFLICT | A trip with the same title already exists for this user |
| 422  | VALIDATION_ERROR | Title is empty, privacy value unknown, date ordering invalid |
| 503  | TRIP_SERVICE_UNAVAILABLE | Database temporarily unavailable |
""",
    responses={
        201: {
            "description": "Trip created.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "trip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            "owner_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                            "title": "Weekend in Lisbon",
                            "status": "draft",
                            "privacy": "private",
                            "departure_date": "2027-06-01",
                            "return_date": "2027-06-07",
                            "is_date_flexible": False,
                            "version": 1,
                            "created_at": "2026-07-02T10:00:00Z",
                            "updated_at": "2026-07-02T10:00:00Z",
                            "deleted_at": None,
                        }
                    }
                }
            },
        },
        409: {
            "description": "A trip with this title already exists for the user.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/trips/conflict",
                        "title": "Conflict",
                        "status": 409,
                        "detail": "A trip titled 'Weekend in Lisbon' already exists.",
                        "instance": "/api/v1/trips",
                        "error_code": "TRIP_CONFLICT",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        422: {
            "description": "Validation error.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/validation-error",
                        "title": "Validation Error",
                        "status": 422,
                        "detail": "Title cannot be empty.",
                        "instance": "/api/v1/trips",
                        "error_code": "VALIDATION_ERROR",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
    },
)
async def create_trip(
    body: TripCreateRequest,
    auth: RequireAuthentication,
    handler: CurrentCreateTripHandler,
) -> Response:
    """
    POST /api/v1/trips — Route handler.

    Translation-only: Pydantic body → CreateTripCommand → handler → HTTP response.
    """
    trace_id = get_request_id() or ""

    command = CreateTripCommand(
        owner_id=auth.user_id,
        title=body.title,
        privacy=body.privacy or "private",
        departure_date=body.departure_date,
        return_date=body.return_date,
        is_date_flexible=body.is_date_flexible,
    )

    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            logger.info(
                "Create trip failed",
                extra={"error_code": err.code, "user_id": auth.user_id},
            )
            return map_trip_failure(err, trace_id=trace_id, instance=_TRIPS_BASE)
        case Success(value=summary):
            logger.info(
                "Trip created",
                extra={"trip_id": str(summary.trip_id), "user_id": auth.user_id},
            )
            return JSONResponse(
                status_code=201,
                content=DataEnvelope(data=TripResponse.from_summary(summary)).model_dump(
                    mode="json"
                ),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips — List trips                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "",
    status_code=200,
    summary="List trips for the authenticated user",
    operation_id="listTrips",
    response_description="Paginated list of trips.",
    description="""
Return a cursor-paginated list of trips owned by the authenticated user.

Results are ordered **newest-first** (created_at DESC). Only non-deleted trips
are returned.

## Pagination

Pass the `cursor` value from a previous response's `next_cursor` field to
retrieve the next page. When `next_cursor` is null in the response, you are
on the last page.

The cursor is an opaque server-issued token. Do not parse, construct, or
modify it.

## Filtering

Use the `status` query parameter to restrict results to trips in a specific
lifecycle status.
""",
    responses={
        200: {
            "description": "Paginated trip list.",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "items": [
                                {
                                    "trip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                    "owner_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
                                    "title": "Weekend in Lisbon",
                                    "status": "draft",
                                    "privacy": "private",
                                    "departure_date": None,
                                    "return_date": None,
                                    "is_date_flexible": False,
                                    "version": 1,
                                    "created_at": "2026-07-02T10:00:00Z",
                                    "updated_at": "2026-07-02T10:00:00Z",
                                    "deleted_at": None,
                                }
                            ],
                            "next_cursor": None,
                            "has_more": False,
                            "limit": 20,
                        }
                    }
                }
            },
        },
    },
)
async def list_trips(
    auth: RequireAuthentication,
    handler: CurrentListTripsHandler,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum number of trips per page. Clamped to 1–100.",
        ),
    ] = 20,
    cursor: Annotated[
        str | None,
        Query(
            description=(
                "Opaque pagination cursor from a previous response's next_cursor. "
                "Omit to retrieve the first page."
            ),
        ),
    ] = None,
    status: Annotated[
        str | None,
        Query(
            description=(
                "Filter by lifecycle status. "
                'One of: "draft", "planned", "active", "completed", "archived".'
            ),
        ),
    ] = None,
) -> Response:
    """
    GET /api/v1/trips — Route handler.

    Translation-only: query params → ListTripsQuery → handler → HTTP response.
    """
    trace_id = get_request_id() or ""

    query = ListTripsQuery(
        owner_id=auth.user_id,
        requester_id=auth.user_id,
        limit=limit,
        cursor=cursor,
        status_filter=status,
    )

    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            logger.info(
                "List trips failed",
                extra={"error_code": err.code, "user_id": auth.user_id},
            )
            return map_trip_failure(err, trace_id=trace_id, instance=_TRIPS_BASE)
        case Success(value=page):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(data=TripPageResponse.from_page(page)).model_dump(
                    mode="json"
                ),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id} — Get a trip                                              #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}",
    status_code=200,
    summary="Get a trip by ID",
    operation_id="getTrip",
    response_description="Trip details.",
    description="""
Return the full details of a single trip.

## Authorization

Only the trip's owner can retrieve it. Requests from other users return 403.

## Error codes

| HTTP | error_code | Cause |
|------|-----------|-------|
| 403  | TRIP_FORBIDDEN | Authenticated user is not the trip owner |
| 404  | TRIP_NOT_FOUND | No trip with this ID exists for the user |
""",
    responses={
        200: {
            "description": "Trip found.",
        },
        403: {
            "description": "Not the trip owner.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/trips/forbidden",
                        "title": "Forbidden",
                        "status": 403,
                        "detail": "You do not have permission to perform this action.",
                        "instance": "/api/v1/trips/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "error_code": "TRIP_FORBIDDEN",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
        404: {
            "description": "Trip not found.",
            "content": {
                "application/json": {
                    "example": {
                        "type": "https://errors.travix.ai/trips/trip-not-found",
                        "title": "Trip Not Found",
                        "status": 404,
                        "detail": "Trip 'a1b2c3d4-e5f6-7890-abcd-ef1234567890' not found.",
                        "instance": "/api/v1/trips/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "error_code": "TRIP_NOT_FOUND",
                        "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                    }
                }
            },
        },
    },
)
async def get_trip(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentGetTripHandler,
) -> Response:
    """
    GET /api/v1/trips/{trip_id} — Route handler.

    Translation-only: path param → GetTripQuery → handler → HTTP response.
    """
    trace_id = get_request_id() or ""
    instance = f"{_TRIPS_BASE}/{trip_id}"

    query = GetTripQuery(trip_id=trip_id, requester_id=auth.user_id)
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            logger.info(
                "Get trip failed",
                extra={"error_code": err.code, "trip_id": trip_id},
            )
            return map_trip_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(data=TripResponse.from_summary(summary)).model_dump(
                    mode="json"
                ),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id} — Update a trip                                         #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}",
    status_code=200,
    summary="Update a trip",
    operation_id="updateTrip",
    response_description="Updated trip.",
    description="""
Update one or more mutable fields of an existing trip.

All fields are optional. Only fields that are explicitly provided are applied.

## Date range updates

Set `update_dates: true` to modify the date range. When `update_dates` is
false (the default), date fields are ignored and the current date range is
preserved.

To clear the date range: `{"update_dates": true, "departure_date": null}`.

## Status transitions

Valid transitions:
```
draft → planned
draft → archived
planned → active
planned → archived
active → completed
active → archived
completed → archived
```

## Error codes

| HTTP | error_code | Cause |
|------|-----------|-------|
| 403  | TRIP_FORBIDDEN | Not the trip owner |
| 404  | TRIP_NOT_FOUND | Trip does not exist |
| 409  | TRIP_CONFLICT | Title already used by another trip owned by the user |
| 422  | TRIP_INVALID_STATUS_TRANSITION | Requested status transition is not permitted |
| 422  | VALIDATION_ERROR | Invalid field value |
""",
    responses={
        200: {
            "description": "Trip updated.",
        },
        403: {
            "description": "Not the trip owner.",
        },
        404: {
            "description": "Trip not found.",
        },
        409: {
            "description": "Title conflict.",
        },
        422: {
            "description": "Validation or invalid status transition.",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_transition": {
                            "summary": "Invalid status transition",
                            "value": {
                                "type": "https://errors.travix.ai/trips/invalid-status-transition",
                                "title": "Invalid Status Transition",
                                "status": 422,
                                "detail": "Cannot transition trip from 'draft' to 'completed'.",
                                "instance": "/api/v1/trips/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                                "error_code": "TRIP_INVALID_STATUS_TRANSITION",
                                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
                                "from_status": "draft",
                                "to_status": "completed",
                            },
                        },
                    }
                }
            },
        },
    },
)
async def update_trip(
    trip_id: str,
    body: TripUpdateRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdateTripHandler,
) -> Response:
    """
    PATCH /api/v1/trips/{trip_id} — Route handler.

    Translation-only: Pydantic body → UpdateTripCommand → handler → HTTP response.
    """
    trace_id = get_request_id() or ""
    instance = f"{_TRIPS_BASE}/{trip_id}"

    command = UpdateTripCommand(
        trip_id=trip_id,
        requester_id=auth.user_id,
        title=body.title,
        privacy=body.privacy,
        new_status=body.new_status,
        update_dates=body.update_dates,
        departure_date=body.departure_date,
        return_date=body.return_date,
        is_date_flexible=body.is_date_flexible,
    )

    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            logger.info(
                "Update trip failed",
                extra={"error_code": err.code, "trip_id": trip_id},
            )
            return map_trip_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(data=TripResponse.from_summary(summary)).model_dump(
                    mode="json"
                ),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id} — Soft-delete a trip                                   #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}",
    status_code=204,
    summary="Delete a trip",
    operation_id="deleteTrip",
    response_description="Trip deleted.",
    description="""
Soft-delete a trip. The trip's `deleted_at` timestamp is set to now and the
record is excluded from all future list and get operations.

**This action is reversible** via a support request. Physical deletion requires
a GDPR erasure request.

## Error codes

| HTTP | error_code | Cause |
|------|-----------|-------|
| 403  | TRIP_FORBIDDEN | Not the trip owner |
| 404  | TRIP_NOT_FOUND | Trip does not exist or is already deleted |
""",
    responses={
        204: {
            "description": "Trip deleted. No response body.",
        },
        403: {
            "description": "Not the trip owner.",
        },
        404: {
            "description": "Trip not found or already deleted.",
        },
    },
)
async def delete_trip(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentDeleteTripHandler,
) -> Response:
    """
    DELETE /api/v1/trips/{trip_id} — Route handler.

    Translation-only: path param → DeleteTripCommand → handler → 204 or error.
    """
    trace_id = get_request_id() or ""
    instance = f"{_TRIPS_BASE}/{trip_id}"

    command = DeleteTripCommand(trip_id=trip_id, requester_id=auth.user_id)
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            logger.info(
                "Delete trip failed",
                extra={"error_code": err.code, "trip_id": trip_id},
            )
            return map_trip_failure(err, trace_id=trace_id, instance=instance)
        case Success():
            logger.info("Trip deleted", extra={"trip_id": trip_id, "user_id": auth.user_id})
            return Response(status_code=204, headers={"X-Request-ID": trace_id})
