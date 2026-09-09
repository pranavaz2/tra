"""Activity Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging
from typing import Generic, TypeVar

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.activity.infrastructure.dependencies import (
    CurrentActivityService,
)
from app.modules.travel.activity.presentation.error_responses import map_activity_failure
from app.modules.travel.activity.presentation.schemas import (
    ActivityFeedResponse,
    ActivityLogResponse,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Trip Activity Feed"])

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    """Standard API response envelope."""

    model_config = ConfigDict(frozen=True)
    data: T = Field(description="Payload data")


@router.get(
    "/{trip_id}/activities",
    response_model=DataEnvelope[ActivityFeedResponse],
    status_code=status.HTTP_200_OK,
    summary="Get trip activity timeline",
    operation_id="getTripActivities",
)
async def get_trip_activities(
    trip_id: str,
    auth: RequireAuthentication,
    service: CurrentActivityService,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/activities"

    result = await service.get_trip_activities(
        trip_id_str=trip_id,
        requester_id_str=str(auth.user_id),
        limit=limit,
        offset=offset,
    )

    match result:
        case Failure(error=err):
            return map_activity_failure(err, trace_id=trace_id, instance=instance)

        case Success(value=feed_page):
            feed_response = ActivityFeedResponse(
                items=[
                    ActivityLogResponse(
                        activity_id=item.activity_id,
                        trip_id=item.trip_id,
                        actor_id=item.actor_id,
                        actor_name=item.actor_name,
                        action=item.action,
                        entity_type=item.entity_type,
                        entity_id=item.entity_id,
                        title=item.title,
                        description=item.description,
                        metadata=item.metadata,
                        created_at=item.created_at,
                    )
                    for item in feed_page.items
                ],
                total=feed_page.total,
                limit=feed_page.limit,
                offset=feed_page.offset,
                has_more=feed_page.has_more,
            )
            envelope = DataEnvelope(data=feed_response)
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )
