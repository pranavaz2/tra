"""RFC 7807 Problem Details error responses for the Travel Planning presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.planning.domain.errors import (
    ActiveProposalExistsError,
    InvalidProposalStatusTransitionError,
    ProposalAlreadyDeletedError,
    ProposalNotFoundError,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_PLANNING_ERROR_BASE = "https://errors.travix.ai/planning"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _planning_problem(
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
    """Build an RFC 7807 Problem Details body for planning-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_PLANNING_ERROR_BASE}/{slug}",
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
    error_code: str = "PLANNING_VALIDATION_ERROR",
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


def map_planning_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """
    Map a TravixError from PlanningService to an RFC 7807 JSONResponse.
    """
    if isinstance(error, ProposalNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_planning_problem(
                slug="proposal-not-found",
                title="Proposal Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="PROPOSAL_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, TripNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_planning_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, ProposalAlreadyDeletedError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_planning_problem(
                slug="proposal-not-found",
                title="Proposal Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="PROPOSAL_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, ForbiddenError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_planning_problem(
                slug="forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=str(error),
                error_code="PLANNING_FORBIDDEN",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, InvalidProposalStatusTransitionError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_planning_problem(
                slug="invalid-status-transition",
                title="Invalid Status Transition",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
                error_code="PROPOSAL_INVALID_STATUS_TRANSITION",
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
                error_code=getattr(error, "code", "PLANNING_VALIDATION_ERROR").upper(),
            ),
        )

    if isinstance(error, ActiveProposalExistsError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_planning_problem(
                slug="conflict",
                title="Conflict",
                http_status=status.HTTP_409_CONFLICT,
                detail=str(error),
                error_code="ACTIVE_PROPOSAL_EXISTS",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, ConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_planning_problem(
                slug="conflict",
                title="Conflict",
                http_status=status.HTTP_409_CONFLICT,
                detail=str(error),
                error_code="PLANNING_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    if isinstance(error, InfrastructureError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=_planning_problem(
                slug="service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The planning service is temporarily unavailable. Please try again shortly.",
                error_code="PLANNING_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            ),
        )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_planning_problem(
            slug="internal-server-error",
            title="Internal Server Error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
            error_code="PLANNING_INTERNAL_ERROR",
            trace_id=trace_id,
            instance=instance,
        ),
    )
