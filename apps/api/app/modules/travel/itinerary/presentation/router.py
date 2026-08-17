"""Itinerary Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.itinerary.application.commands import (
    AddItineraryDayCommand,
    AddItineraryItemCommand,
    RemoveItineraryDayCommand,
    RemoveItineraryItemCommand,
    UpdateItineraryDayCommand,
    UpdateItineraryItemCommand,
)
from app.modules.travel.itinerary.application.queries import GetItineraryQuery
from app.modules.travel.itinerary.infrastructure.dependencies import (
    CurrentAddItineraryDayHandler,
    CurrentAddItineraryItemHandler,
    CurrentGetItineraryHandler,
    CurrentRemoveItineraryDayHandler,
    CurrentRemoveItineraryItemHandler,
    CurrentUpdateItineraryDayHandler,
    CurrentUpdateItineraryItemHandler,
)
from app.modules.travel.itinerary.presentation.error_responses import map_itinerary_failure
from app.modules.travel.itinerary.presentation.schemas import (
    DataEnvelope,
    ItineraryDayCreateRequest,
    ItineraryDayUpdateRequest,
    ItineraryItemCreateRequest,
    ItineraryItemUpdateRequest,
    ItineraryResponse,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Itineraries"])


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/itinerary — Fetch itinerary                              #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/itinerary",
    response_model=DataEnvelope[ItineraryResponse],
    summary="Get itinerary for a trip",
    operation_id="getItinerary",
    description=(
        "Retrieve the itinerary for a trip. If it doesn't exist, "
        "an empty one is auto-created."
    ),
)
async def get_itinerary(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentGetItineraryHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary"

    query = GetItineraryQuery(trip_id=trip_id, requester_id=str(auth.user_id))
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/itinerary/days — Add a day                              #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/itinerary/days",
    response_model=DataEnvelope[ItineraryResponse],
    status_code=201,
    summary="Add a day to the itinerary",
    operation_id="addItineraryDay",
)
async def add_day(
    trip_id: str,
    body: ItineraryDayCreateRequest,
    auth: RequireAuthentication,
    handler: CurrentAddItineraryDayHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary/days"

    command = AddItineraryDayCommand(
        trip_id=trip_id,
        requester_id=str(auth.user_id),
        day_number=body.day_number,
        title=body.title,
        date=body.date,
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/itinerary/days/{day_id} — Update a day                  #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/itinerary/days/{day_id}",
    response_model=DataEnvelope[ItineraryResponse],
    summary="Update a day in the itinerary",
    operation_id="updateItineraryDay",
)
async def update_day(
    trip_id: str,
    day_id: str,
    body: ItineraryDayUpdateRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdateItineraryDayHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary/days/{day_id}"

    command = UpdateItineraryDayCommand(
        trip_id=trip_id,
        day_id=day_id,
        requester_id=str(auth.user_id),
        day_number=body.day_number,
        title=body.title,
        date=body.date,
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id}/itinerary/days/{day_id} — Remove a day                #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}/itinerary/days/{day_id}",
    response_model=DataEnvelope[ItineraryResponse],
    summary="Remove a day from the itinerary",
    operation_id="removeItineraryDay",
)
async def remove_day(
    trip_id: str,
    day_id: str,
    auth: RequireAuthentication,
    handler: CurrentRemoveItineraryDayHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary/days/{day_id}"

    command = RemoveItineraryDayCommand(
        trip_id=trip_id,
        day_id=day_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/itinerary/items — Add an item                           #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/itinerary/items",
    response_model=DataEnvelope[ItineraryResponse],
    status_code=201,
    summary="Add an item to a day in the itinerary",
    operation_id="addItineraryItem",
)
async def add_item(
    trip_id: str,
    body: ItineraryItemCreateRequest,
    auth: RequireAuthentication,
    handler: CurrentAddItineraryItemHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary/items"

    command = AddItineraryItemCommand(
        trip_id=trip_id,
        day_id=str(body.day_id),
        requester_id=str(auth.user_id),
        title=body.title,
        item_type=body.item_type.value,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        location_id=str(body.location_id) if body.location_id else None,
        cost=body.cost,
        currency=body.currency,
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/itinerary/items/{item_id} — Update an item            #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/itinerary/items/{item_id}",
    response_model=DataEnvelope[ItineraryResponse],
    summary="Update an itinerary item",
    operation_id="updateItineraryItem",
)
async def update_item(
    trip_id: str,
    item_id: str,
    body: ItineraryItemUpdateRequest,
    auth: RequireAuthentication,
    handler: CurrentUpdateItineraryItemHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary/items/{item_id}"

    command = UpdateItineraryItemCommand(
        trip_id=trip_id,
        item_id=item_id,
        requester_id=str(auth.user_id),
        day_id=str(body.day_id) if body.day_id else None,
        title=body.title,
        item_type=body.item_type.value,
        description=body.description,
        start_time=body.start_time,
        end_time=body.end_time,
        location_id=str(body.location_id) if body.location_id else None,
        cost=body.cost,
        currency=body.currency,
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id}/itinerary/items/{item_id} — Remove an item            #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}/itinerary/items/{item_id}",
    response_model=DataEnvelope[ItineraryResponse],
    summary="Remove an item from the itinerary",
    operation_id="removeItineraryItem",
)
async def remove_item(
    trip_id: str,
    item_id: str,
    auth: RequireAuthentication,
    handler: CurrentRemoveItineraryItemHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/itinerary/items/{item_id}"

    command = RemoveItineraryItemCommand(
        trip_id=trip_id,
        item_id=item_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_itinerary_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=ItineraryResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )
