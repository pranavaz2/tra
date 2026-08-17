"""RFC 7807 Problem Details error responses for the Itineraries presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.itinerary.domain.errors import (
    ItineraryAlreadyDeletedError,
    ItineraryAlreadyExistsError,
    ItineraryDayAlreadyExistsError,
    ItineraryDayNotFoundError,
    ItineraryItemNotFoundError,
    ItineraryNotFoundError,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_ITINERARY_ERROR_BASE = "https://errors.travix.ai/itineraries"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _itinerary_problem(
    *,
    slug: str,
    title: str,
    http_status: int,
    detail: str,
    error_code: str,
    trace_id: str,
    instance: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an RFC 7807 Problem Details body for itinerary-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_ITINERARY_ERROR_BASE}/{slug}",
        "title": title,
        "status": http_status,
        "detail": detail,
        "instance": instance,
        "error_code": error_code,
        "trace_id": trace_id,
    }
    if extra:
        body.update(extra)
    return body


def _validation_problem(
    *,
    trace_id: str,
    detail: str,
    instance: str,
    field: str | None = None,
    error_code: str = "ITINERARY_VALIDATION_ERROR",
) -> dict[str, Any]:
    """Build an RFC 7807 body for validation errors."""
    body: dict[str, Any] = {
        "type": _VALIDATION_ERROR_TYPE,
        "title": "Validation Error",
        "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
        "detail": detail,
        "instance": instance,
        "error_code": "VALIDATION_ERROR",
        "trace_id": trace_id,
    }
    if field:
        body["errors"] = [
            {
                "field": field,
                "error_code": error_code,
                "message": detail,
            }
        ]
    return body


def map_itinerary_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """Map a TravixError to an RFC 7807 JSONResponse."""
    match error:
        case TripNotFoundError():
            body = _itinerary_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case ItineraryNotFoundError() | ItineraryAlreadyDeletedError():
            body = _itinerary_problem(
                slug="itinerary-not-found",
                title="Itinerary Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="ITINERARY_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case ItineraryDayNotFoundError():
            body = _itinerary_problem(
                slug="day-not-found",
                title="Day Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="ITINERARY_DAY_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case ItineraryItemNotFoundError():
            body = _itinerary_problem(
                slug="item-not-found",
                title="Item Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="ITINERARY_ITEM_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case ItineraryAlreadyExistsError():
            body = _itinerary_problem(
                slug="itinerary-conflict",
                title="Itinerary Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="ITINERARY_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case ItineraryDayAlreadyExistsError():
            body = _itinerary_problem(
                slug="day-conflict",
                title="Day Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="ITINERARY_DAY_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case ForbiddenError():
            body = _itinerary_problem(
                slug="itinerary-forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=error.message,
                error_code="ITINERARY_FORBIDDEN",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_403_FORBIDDEN)

        case ValidationError():
            body = _validation_problem(
                trace_id=trace_id,
                detail=error.message,
                instance=instance,
                field=getattr(error, "field", None),
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case InfrastructureError():
            body = _itinerary_problem(
                slug="itinerary-service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The itinerary service is temporarily unavailable. Please try again later.",
                error_code="ITINERARY_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        case _:
            body = _itinerary_problem(
                slug="itinerary-internal-error",
                title="Internal Server Error",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred.",
                error_code="ITINERARY_INTERNAL_ERROR",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
