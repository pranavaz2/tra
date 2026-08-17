"""RFC 7807 Problem Details error responses for the Recommendations presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.recommendations.domain.errors import UserPreferencesNotFoundError
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_REC_ERROR_BASE = "https://errors.travix.ai/recommendations"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _rec_problem(
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
    """Build an RFC 7807 Problem Details body for recommendation-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_REC_ERROR_BASE}/{slug}",
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
    error_code: str = "RECOMMENDATION_VALIDATION_ERROR",
) -> dict[str, Any]:
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


def map_recommendation_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """Map a TravixError to an RFC 7807 JSONResponse."""
    match error:
        case UserPreferencesNotFoundError():
            body = _rec_problem(
                slug="user-preferences-not-found",
                title="User Preferences Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="USER_PREFERENCES_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case ValidationError():
            body = _validation_problem(
                trace_id=trace_id,
                detail=error.message,
                instance=instance,
                field=getattr(error, "field", None),
                error_code=getattr(error, "error_code", "RECOMMENDATION_VALIDATION_ERROR"),
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case ForbiddenError():
            body = _rec_problem(
                slug="forbidden",
                title="Forbidden Action",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=error.message,
                error_code="FORBIDDEN_ACTION",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_403_FORBIDDEN)

        case InfrastructureError():
            body = _rec_problem(
                slug="infrastructure-error",
                title="Infrastructure Error",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A service failure occurred. Please try again later.",
                error_code="SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        case _:
            body = _rec_problem(
                slug="internal-server-error",
                title="Internal Server Error",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred.",
                error_code="INTERNAL_SERVER_ERROR",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
