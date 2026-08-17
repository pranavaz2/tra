"""RFC 7807 Problem Details error responses for the Media presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.media.domain.errors import (
    CaptionLengthExceededError,
    DuplicateMediaIdError,
    MaxFileSizeExceededError,
    MediaCollectionAlreadyExistsError,
    MediaCollectionAlreadyLockedError,
    MediaCollectionNotFoundError,
    MediaItemNotFoundError,
    MimeTypeNotSupportedError,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_MEDIA_ERROR_BASE = "https://errors.travix.ai/media"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _media_problem(
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
    """Build an RFC 7807 Problem Details body for media-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_MEDIA_ERROR_BASE}/{slug}",
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
    error_code: str = "MEDIA_VALIDATION_ERROR",
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


def map_media_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """Map a TravixError to an RFC 7807 JSONResponse."""
    match error:
        case TripNotFoundError():
            body = _media_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case MediaCollectionNotFoundError():
            body = _media_problem(
                slug="media-collection-not-found",
                title="Media Collection Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="MEDIA_COLLECTION_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case MediaItemNotFoundError():
            body = _media_problem(
                slug="media-item-not-found",
                title="Media Item Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="MEDIA_ITEM_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case MediaCollectionAlreadyExistsError():
            body = _media_problem(
                slug="media-collection-conflict",
                title="Media Collection Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="MEDIA_COLLECTION_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case DuplicateMediaIdError():
            body = _media_problem(
                slug="duplicate-media-id",
                title="Duplicate Media ID",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.message,
                error_code="DUPLICATE_MEDIA_ID",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case MimeTypeNotSupportedError():
            body = _media_problem(
                slug="mime-type-not-supported",
                title="MIME Type Not Supported",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.message,
                error_code="MIME_TYPE_NOT_SUPPORTED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case MaxFileSizeExceededError():
            body = _media_problem(
                slug="max-file-size-exceeded",
                title="Max File Size Exceeded",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.message,
                error_code="MAX_FILE_SIZE_EXCEEDED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case CaptionLengthExceededError():
            body = _media_problem(
                slug="caption-length-exceeded",
                title="Caption Length Exceeded",
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error.message,
                error_code="CAPTION_LENGTH_EXCEEDED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

        case MediaCollectionAlreadyLockedError():
            body = _media_problem(
                slug="media-collection-locked",
                title="Media Collection Locked",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="MEDIA_COLLECTION_LOCKED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case ForbiddenError():
            body = _media_problem(
                slug="media-forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=error.message,
                error_code="MEDIA_FORBIDDEN",
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
            body = _media_problem(
                slug="media-service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The media storage or verification service is temporarily unavailable.",
                error_code="MEDIA_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        case _:
            body = _media_problem(
                slug="media-internal-error",
                title="Internal Server Error",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred in media module.",
                error_code="MEDIA_INTERNAL_ERROR",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
