"""Media Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.media.application.commands import (
    AttachMediaToActivityCommand,
    AttachMediaToExpenseCommand,
    DeleteMediaCommand,
    UpdateCaptionCommand,
    UploadMediaCommand,
)
from app.modules.travel.media.application.queries import (
    GetMediaQuery,
    ListMediaQuery,
)
from app.modules.travel.media.infrastructure.dependencies import (
    CurrentAttachMediaToActivityHandler,
    CurrentAttachMediaToExpenseHandler,
    CurrentDeleteMediaHandler,
    CurrentGetMediaHandler,
    CurrentListMediaHandler,
    CurrentUpdateCaptionHandler,
    CurrentUploadMediaHandler,
)
from app.modules.travel.media.presentation.error_responses import map_media_failure
from app.modules.travel.media.presentation.schemas import (
    AttachActivityRequest,
    AttachExpenseRequest,
    DataEnvelope,
    MediaCaptionUpdateRequest,
    MediaItemResponse,
    MediaListResponse,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Trip Media"])


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/media — Upload media                                    #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/media",
    response_model=DataEnvelope[MediaItemResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload media",
    operation_id="uploadMedia",
)
async def upload_media(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentUploadMediaHandler,
    file: UploadFile = File(...),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media"

    try:
        content = await file.read()
    except Exception as exc:
        return map_media_failure(
            __import__("app.shared.domain.errors", fromlist=["ValidationError"]).ValidationError(
                f"Failed to read upload file: {exc!s}"
            ),
            trace_id=trace_id,
            instance=instance,
        )

    command = UploadMediaCommand(
        trip_id=trip_id,
        file_name=file.filename or "file",
        file_content=content,
        mime_type=file.content_type or "application/octet-stream",
        uploaded_by=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=MediaItemResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/media — List media with cursor pagination                #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/media",
    response_model=DataEnvelope[MediaListResponse],
    summary="List trip media",
    operation_id="listTripMedia",
)
async def list_trip_media(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentListMediaHandler,
    limit: int = Query(20, ge=1, le=100, description="Page limit."),
    cursor: str | None = Query(None, description="Keyset pagination cursor."),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media"

    query = ListMediaQuery(
        trip_id=trip_id,
        requester_id=str(auth.user_id),
        limit=limit,
        cursor=cursor,
    )
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=page):
            envelope = DataEnvelope(data=MediaListResponse.model_validate(page))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/media/{media_id} — Get single media item                 #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/media/{media_id}",
    response_model=DataEnvelope[MediaItemResponse],
    summary="Get single media item",
    operation_id="getMediaItem",
)
async def get_media_item(
    trip_id: str,
    media_id: str,
    auth: RequireAuthentication,
    handler: CurrentGetMediaHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media/{media_id}"

    query = GetMediaQuery(
        trip_id=trip_id,
        media_id=media_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=MediaItemResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/media/{media_id} — Update caption                      #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/media/{media_id}",
    response_model=DataEnvelope[MediaItemResponse],
    summary="Update caption",
    operation_id="updateMediaCaption",
)
async def update_media_caption(
    trip_id: str,
    media_id: str,
    body: MediaCaptionUpdateRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdateCaptionHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media/{media_id}"

    command = UpdateCaptionCommand(
        trip_id=trip_id,
        media_id=media_id,
        caption=body.caption,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=MediaItemResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id}/media/{media_id} — Soft delete media                  #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}/media/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media item",
    operation_id="deleteMediaItem",
)
async def delete_media_item(
    trip_id: str,
    media_id: str,
    auth: RequireAuthentication,
    handler: CurrentDeleteMediaHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media/{media_id}"

    command = DeleteMediaCommand(
        trip_id=trip_id,
        media_id=media_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success():
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/media/{media_id}/activity — Attach to activity          #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/media/{media_id}/activity",
    response_model=DataEnvelope[MediaItemResponse],
    summary="Attach media to activity",
    operation_id="attachMediaToActivity",
)
async def attach_media_to_activity(
    trip_id: str,
    media_id: str,
    body: AttachActivityRequest,
    auth: RequireAuthentication,
    handler: CurrentAttachMediaToActivityHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media/{media_id}/activity"

    command = AttachMediaToActivityCommand(
        trip_id=trip_id,
        media_id=media_id,
        activity_id=body.activity_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=MediaItemResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/media/{media_id}/expense — Attach to expense            #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/media/{media_id}/expense",
    response_model=DataEnvelope[MediaItemResponse],
    summary="Attach media to expense",
    operation_id="attachMediaToExpense",
)
async def attach_media_to_expense(
    trip_id: str,
    media_id: str,
    body: AttachExpenseRequest,
    auth: RequireAuthentication,
    handler: CurrentAttachMediaToExpenseHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/media/{media_id}/expense"

    command = AttachMediaToExpenseCommand(
        trip_id=trip_id,
        media_id=media_id,
        expense_id=body.expense_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_media_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=MediaItemResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )
