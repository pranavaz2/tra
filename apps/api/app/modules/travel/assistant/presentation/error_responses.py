"""RFC 7807 Problem Details error responses for the Travel Assistant presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.assistant.domain.errors import (
    ActionAlreadyExecutedError,
    ActionPermissionError,
    ActionValidationError,
    AssistantError,
    ProposedActionNotFoundError,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.shared.domain.errors import (
    ConflictError,
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_ASSISTANT_ERROR_BASE = "https://errors.travix.ai/assistant"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _assistant_problem(
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
    """Build an RFC 7807 Problem Details body for assistant errors."""
    body: dict[str, Any] = {
        "type": f"{_ASSISTANT_ERROR_BASE}/{slug}",
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


def map_assistant_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """Map any TravixError encountered in the assistant layer to an RFC 7807 JSONResponse."""
    headers = {"Content-Type": "application/problem+json"}

    # 1. Proposed Action Not Found (404)
    if isinstance(error, ProposedActionNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_assistant_problem(
                slug="action-not-found",
                title="Proposed Action Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="ASSISTANT_ACTION_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
                extra={"action_id": error.action_id},
            ),
            headers=headers,
        )

    # 2. Trip Not Found (404)
    if isinstance(error, TripNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=_assistant_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=str(error),
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            ),
            headers=headers,
        )

    # 3. Action Already Executed / State Conflict (409)
    if isinstance(error, ActionAlreadyExecutedError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_assistant_problem(
                slug="action-already-executed",
                title="Proposed Action Already Executed",
                http_status=status.HTTP_409_CONFLICT,
                detail=str(error),
                error_code="ACTION_ALREADY_EXECUTED",
                trace_id=trace_id,
                instance=instance,
                extra={"action_id": error.action_id, "status": error.status},
            ),
            headers=headers,
        )

    # 4. Permission / Forbidden (403)
    if isinstance(error, (ForbiddenError, ActionPermissionError)):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=_assistant_problem(
                slug="forbidden",
                title="Forbidden Action",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=str(error),
                error_code="FORBIDDEN",
                trace_id=trace_id,
                instance=instance,
            ),
            headers=headers,
        )

    # 5. Validation Error (422 / 400)
    if isinstance(error, (ValidationError, ActionValidationError)):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_assistant_problem(
                slug="validation-error",
                title="Validation Error",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
                error_code="VALIDATION_ERROR",
                trace_id=trace_id,
                instance=instance,
            ),
            headers=headers,
        )

    # 6. Default Internal / Infrastructure Error (500)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_assistant_problem(
            slug="internal-error",
            title="Internal Server Error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(error),
            error_code="INTERNAL_SERVER_ERROR",
            trace_id=trace_id,
            instance=instance,
        ),
        headers=headers,
    )
