"""Export Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.export.infrastructure.dependencies import (
    CurrentExportService,
)
from app.modules.travel.export.presentation.error_responses import map_export_failure
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Trip Export"])


@router.get(
    "/{trip_id}/export/ical",
    status_code=status.HTTP_200_OK,
    summary="Export trip itinerary as iCalendar (.ics)",
    operation_id="exportTripICal",
    responses={
        200: {
            "content": {"text/calendar": {}},
            "description": "Standard RFC 5545 iCalendar file.",
        }
    },
)
async def export_trip_ical(
    trip_id: str,
    auth: RequireAuthentication,
    service: CurrentExportService,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/export/ical"

    result = await service.export_ical(
        trip_id_str=trip_id,
        requester_id_str=str(auth.user_id),
    )

    match result:
        case Failure(error=err):
            return map_export_failure(err, trace_id=trace_id, instance=instance)

        case Success(value=ical_content):
            filename = f"trip-{trip_id}.ics"
            return Response(
                content=ical_content,
                media_type="text/calendar; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Request-ID": trace_id,
                },
            )


@router.get(
    "/{trip_id}/export/pdf",
    status_code=status.HTTP_200_OK,
    summary="Export trip itinerary and budget summary as PDF",
    operation_id="exportTripPDF",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Formatted itinerary PDF document.",
        }
    },
)
async def export_trip_pdf(
    trip_id: str,
    auth: RequireAuthentication,
    service: CurrentExportService,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/export/pdf"

    result = await service.export_pdf(
        trip_id_str=trip_id,
        requester_id_str=str(auth.user_id),
    )

    match result:
        case Failure(error=err):
            return map_export_failure(err, trace_id=trace_id, instance=instance)

        case Success(value=pdf_bytes):
            filename = f"trip-{trip_id}-itinerary.pdf"
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "X-Request-ID": trace_id,
                },
            )
