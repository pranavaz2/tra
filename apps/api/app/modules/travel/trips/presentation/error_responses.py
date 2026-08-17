"""
RFC 7807 Problem Details error responses for the Trips presentation layer.

All error responses follow the RFC 7807 format (type, title, status, detail,
instance) extended with Travix-specific fields (error_code, trace_id).

Error type URI convention:
  https://errors.travix.ai/trips/<kebab-case-error-name>

No HTTP exceptions are raised — all failures produce a JSONResponse directly
so the caller can return it without try/except.

Error hierarchy mapped (most specific first within each handler):
  TripNotFoundError           → 404 TRIP_NOT_FOUND
  TripAlreadyDeletedError     → 404 TRIP_NOT_FOUND (trip is logically gone)
  ForbiddenError              → 403 TRIP_FORBIDDEN
  InvalidTripStatusTransitionError → 422 TRIP_INVALID_STATUS_TRANSITION
  ValidationError             → 422 VALIDATION_ERROR (with field info)
  ConflictError               → 409 TRIP_CONFLICT
  InfrastructureError         → 503 TRIP_SERVICE_UNAVAILABLE
  TravixError (other)         → 500 TRIP_INTERNAL_ERROR

Security:
  503 and 500 responses never leak internal error messages or stack traces.
  Only generic messages are returned to the client.
"""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.trips.domain.errors import (
    InvalidTripStatusTransitionError,
    TripAlreadyDeletedError,
    TripNotFoundError,
)
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_TRIP_ERROR_BASE = "https://errors.travix.ai/trips"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _trip_problem(
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
    """Build an RFC 7807 Problem Details body for trip-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_TRIP_ERROR_BASE}/{slug}",
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
    error_code: str = "TRIP_VALIDATION_ERROR",
) -> dict[str, Any]:
    """Build an RFC 7807 + field-errors body for 422 validation failures."""
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


def map_trip_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """
    Map a TravixError from TripService to an RFC 7807 JSONResponse.

    Called by route handlers when result.is_ok is False. Checks error types
    most-specific first to avoid branch shadowing.

    Error hierarchy checked:
      TripNotFoundError             → 404 TRIP_NOT_FOUND
      TripAlreadyDeletedError       → 404 TRIP_NOT_FOUND
      ForbiddenError                → 403 TRIP_FORBIDDEN
      InvalidTripStatusTransitionError → 422 TRIP_INVALID_STATUS_TRANSITION
      ValidationError               → 422 VALIDATION_ERROR
      ConflictError                 → 409 TRIP_CONFLICT
      InfrastructureError           → 503 TRIP_SERVICE_UNAVAILABLE
      TravixError (other)           → 500 TRIP_INTERNAL_ERROR

    Security: 503 and 500 bodies never contain internal error details.
    """
    if isinstance(error, TripNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_trip_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # TripAlreadyDeletedError: soft-deleted trips are treated as not found
    # for the client — the resource is logically absent.
    if isinstance(error, TripAlreadyDeletedError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_trip_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, ForbiddenError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_trip_problem(
                slug="forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=str(error),
                error_code="TRIP_FORBIDDEN",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # Check InvalidTripStatusTransitionError before ValidationError —
    # it is a DomainError (not a subclass of ValidationError) and carries
    # structured from_status / to_status fields.
    if isinstance(error, InvalidTripStatusTransitionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_trip_problem(
                slug="invalid-status-transition",
                title="Invalid Status Transition",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
                error_code="TRIP_INVALID_STATUS_TRANSITION",
                trace_id=trace_id,
                instance=instance,
                extra={
                    "from_status": error.from_status,
                    "to_status": error.to_status,
                },
            ),
        )

    if isinstance(error, ValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_validation_problem(
                trace_id=trace_id,
                detail=str(error),
                instance=instance,
                field=getattr(error, "field", None),
                error_code=getattr(error, "code", "TRIP_VALIDATION_ERROR").upper(),
            ),
        )

    if isinstance(error, ConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_trip_problem(
                slug="conflict",
                title="Conflict",
                http_status=status.HTTP_409_CONFLICT,
                detail=str(error),
                error_code="TRIP_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # InfrastructureError and its subclasses (DatabaseError, CacheError, etc.)
    if isinstance(error, InfrastructureError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_trip_problem(
                slug="service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The trip service is temporarily unavailable. Please try again shortly.",
                error_code="TRIP_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    # Unexpected TravixError subtype → 500
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_trip_problem(
            slug="internal-server-error",
            title="Internal Server Error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
            error_code="TRIP_INTERNAL_ERROR",
            trace_id=trace_id,
            instance=instance,
        ),
    )
