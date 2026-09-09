"""RFC 7807 Problem Details error responses for the Notifications presentation layer."""

from __future__ import annotations

from typing import Any
from fastapi import status
from fastapi.responses import JSONResponse

from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    NotFoundError,
    TravixError,
    ValidationError,
)

_NOTIFICATIONS_ERROR_BASE = "https://errors.travix.ai/notifications"


def _notifications_problem(
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
    body: dict[str, Any] = {
        "type": f"{_NOTIFICATIONS_ERROR_BASE}/{slug}",
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


def map_notifications_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    if isinstance(error, NotFoundError):
        body = _notifications_problem(
            slug="not-found",
            title="Resource Not Found",
            http_status=status.HTTP_404_NOT_FOUND,
            detail=str(error),
            error_code="RESOURCE_NOT_FOUND",
            trace_id=trace_id,
            instance=instance,
        )
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=body)

    if isinstance(error, ForbiddenError):
        body = _notifications_problem(
            slug="forbidden",
            title="Access Forbidden",
            http_status=status.HTTP_403_FORBIDDEN,
            detail=str(error),
            error_code="ACCESS_FORBIDDEN",
            trace_id=trace_id,
            instance=instance,
        )
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=body)

    if isinstance(error, ValidationError):
        body = _notifications_problem(
            slug="validation-error",
            title="Validation Error",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
            error_code="VALIDATION_ERROR",
            trace_id=trace_id,
            instance=instance,
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=body)

    body = _notifications_problem(
        slug="internal-error",
        title="Internal Server Error",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred in notifications.",
        error_code="INTERNAL_SERVER_ERROR",
        trace_id=trace_id,
        instance=instance,
    )
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=body)
