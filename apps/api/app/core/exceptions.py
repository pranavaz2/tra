"""
Travix AI — Global Exception Handlers

Registers FastAPI exception handlers that format all error responses using
RFC 7807 Problem Details (https://datatracker.ietf.org/doc/html/rfc7807).

Error response schema:
  {
    "type":     "https://travixai.com/errors/{error-slug}",
    "title":    "Human-readable error title",
    "status":   422,
    "detail":   "Specific description or structured validation errors",
    "instance": "/api/v1/trips/123"
  }

All module-specific exceptions must be defined in their own
{module}/exceptions.py file and re-raised as HTTPException where needed,
or handled by a dedicated exception handler registered here.
"""

from __future__ import annotations

import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_ERROR_BASE = "https://travixai.com/errors"


def _problem_detail(
    type_slug: str,
    title: str,
    http_status: int,
    detail: object,
    instance: str,
) -> dict[str, object]:
    return {
        "type": f"{_ERROR_BASE}/{type_slug}",
        "title": title,
        "status": http_status,
        "detail": detail,
        "instance": instance,
    }


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Convert Pydantic validation errors to RFC 7807 format (422)."""
    logger.warning(
        "Request validation failed",
        extra={"path": str(request.url.path), "error_count": len(exc.errors())},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_problem_detail(
            type_slug="validation-error",
            title="Validation Error",
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
            instance=str(request.url),
        ),
    )


async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions (500).

    Logs the full traceback for internal visibility but returns a safe,
    non-leaking message to the client. Never expose stack traces externally.
    """
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_problem_detail(
            type_slug="internal-server-error",
            title="Internal Server Error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again later.",
            instance=str(request.url),
        ),
    )
