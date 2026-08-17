"""RFC 7807 Problem Details error responses for the Sharing presentation layer."""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse

from app.modules.travel.sharing.domain.errors import (
    CannotChangeOwnerRoleError,
    CannotRemoveOwnerError,
    CollaborationAlreadyExistsError,
    CollaborationAlreadyLockedError,
    CollaborationNotFoundError,
    InvitationAlreadyExistsError,
    InvitationNotFoundError,
    InvalidInvitationStatusError,
    MemberNotFoundError,
    OnlyOwnerCanModifyError,
    PublicSharingNotEnabledError,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)

_SHARING_ERROR_BASE = "https://errors.travix.ai/sharing"
_VALIDATION_ERROR_TYPE = "https://errors.travix.ai/validation-error"


def _sharing_problem(
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
    """Build an RFC 7807 Problem Details body for sharing-domain errors."""
    body: dict[str, Any] = {
        "type": f"{_SHARING_ERROR_BASE}/{slug}",
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
    error_code: str = "SHARING_VALIDATION_ERROR",
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


def map_sharing_failure(
    error: TravixError,
    *,
    trace_id: str,
    instance: str,
) -> JSONResponse:
    """Map a TravixError to an RFC 7807 JSONResponse."""
    match error:
        case TripNotFoundError():
            body = _sharing_problem(
                slug="trip-not-found",
                title="Trip Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="TRIP_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case CollaborationNotFoundError():
            body = _sharing_problem(
                slug="collaboration-not-found",
                title="Collaboration Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="COLLABORATION_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case MemberNotFoundError():
            body = _sharing_problem(
                slug="member-not-found",
                title="Member Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="MEMBER_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case InvitationNotFoundError():
            body = _sharing_problem(
                slug="invitation-not-found",
                title="Invitation Not Found",
                http_status=status.HTTP_404_NOT_FOUND,
                detail=error.message,
                error_code="INVITATION_NOT_FOUND",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_404_NOT_FOUND)

        case CollaborationAlreadyExistsError():
            body = _sharing_problem(
                slug="collaboration-conflict",
                title="Collaboration Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="COLLABORATION_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case InvitationAlreadyExistsError():
            body = _sharing_problem(
                slug="invitation-conflict",
                title="Invitation Already Exists",
                http_status=status.HTTP_409_CONFLICT,
                detail=error.message,
                error_code="INVITATION_CONFLICT",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_409_CONFLICT)

        case CollaborationAlreadyLockedError():
            body = _sharing_problem(
                slug="collaboration-locked",
                title="Collaboration Locked",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="COLLABORATION_LOCKED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case CannotRemoveOwnerError():
            body = _sharing_problem(
                slug="cannot-remove-owner",
                title="Cannot Remove Owner",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="CANNOT_REMOVE_OWNER",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case CannotChangeOwnerRoleError():
            body = _sharing_problem(
                slug="cannot-change-owner-role",
                title="Cannot Change Owner Role",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="CANNOT_CHANGE_OWNER_ROLE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case InvalidInvitationStatusError():
            body = _sharing_problem(
                slug="invalid-invitation-status",
                title="Invalid Invitation Status",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="INVALID_INVITATION_STATUS",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case PublicSharingNotEnabledError():
            body = _sharing_problem(
                slug="public-sharing-not-enabled",
                title="Public Sharing Not Enabled",
                http_status=status.HTTP_400_BAD_REQUEST,
                detail=error.message,
                error_code="PUBLIC_SHARING_NOT_ENABLED",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_400_BAD_REQUEST)

        case OnlyOwnerCanModifyError():
            body = _sharing_problem(
                slug="sharing-forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=error.message,
                error_code="ONLY_OWNER_CAN_MODIFY",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_403_FORBIDDEN)

        case ForbiddenError():
            body = _sharing_problem(
                slug="sharing-forbidden",
                title="Forbidden",
                http_status=status.HTTP_403_FORBIDDEN,
                detail=error.message,
                error_code="SHARING_FORBIDDEN",
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
            body = _sharing_problem(
                slug="sharing-service-unavailable",
                title="Service Unavailable",
                http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The sharing service is temporarily unavailable. Please try again later.",
                error_code="SHARING_SERVICE_UNAVAILABLE",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        case _:
            body = _sharing_problem(
                slug="sharing-internal-error",
                title="Internal Server Error",
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected error occurred.",
                error_code="SHARING_INTERNAL_ERROR",
                trace_id=trace_id,
                instance=instance,
            )
            return JSONResponse(body, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
