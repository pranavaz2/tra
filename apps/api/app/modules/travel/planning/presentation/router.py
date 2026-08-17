"""Travel Planning API Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.planning.application.commands import (
    AcceptProposalCommand,
    RejectProposalCommand,
    RequestProposalCommand,
)
from app.modules.travel.planning.application.queries import (
    GetProposalByTripQuery,
    GetProposalQuery,
    ListProposalsQuery,
)
from app.modules.travel.planning.infrastructure.dependencies import (
    CurrentAcceptProposalHandler,
    CurrentGetProposalByTripHandler,
    CurrentGetProposalHandler,
    CurrentListProposalsHandler,
    CurrentRejectProposalHandler,
    CurrentRequestProposalHandler,
)
from app.modules.travel.planning.presentation.error_responses import map_planning_failure
from app.modules.travel.planning.presentation.schemas import (
    DataEnvelope,
    ProposalCreateRequest,
    ProposalPageResponse,
    ProposalResponse,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Planning"])

_PLANNING_BASE = "/api/v1/planning"
_TRIPS_BASE = "/api/v1/trips"


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/planning/proposals — Request a proposal                #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/trips/{trip_id}/planning/proposals",
    status_code=201,
    summary="Request a new travel proposal",
    operation_id="requestProposal",
    response_description="Proposal successfully queued and generated.",
    responses={
        201: {"description": "Proposal created and generated."},
        404: {"description": "Trip not found."},
        403: {"description": "Not the trip owner."},
        409: {"description": "Conflict with another active proposal generation."},
        422: {"description": "Validation error on preferences."},
    },
)
async def request_proposal(
    trip_id: str,
    body: ProposalCreateRequest,
    auth: RequireAuthentication,
    handler: CurrentRequestProposalHandler,
) -> Response:
    """Request a new AI-generated travel proposal for a trip."""
    trace_id = get_request_id() or ""
    instance = f"{_TRIPS_BASE}/{trip_id}/planning/proposals"

    command = RequestProposalCommand(
        trip_id=trip_id,
        requester_id=auth.user_id,
        destination=body.destination,
        duration_days=body.duration_days,
        budget_level=body.budget_level,
        interests=body.interests,
        travel_style=body.travel_style,
        special_requirements=body.special_requirements,
    )

    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_planning_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=201,
                content=DataEnvelope(
                    data=ProposalResponse.from_dto(summary)
                ).model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /planning/proposals/{proposal_id} — Get proposal by ID                  #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/planning/proposals/{proposal_id}",
    status_code=200,
    summary="Get a proposal by ID",
    operation_id="getProposal",
    response_description="Proposal details.",
    responses={
        200: {"description": "Proposal found."},
        404: {"description": "Proposal not found."},
        403: {"description": "Not the proposal owner."},
    },
)
async def get_proposal(
    proposal_id: str,
    auth: RequireAuthentication,
    handler: CurrentGetProposalHandler,
) -> Response:
    """Retrieve details of a single proposal."""
    trace_id = get_request_id() or ""
    instance = f"{_PLANNING_BASE}/proposals/{proposal_id}"

    query = GetProposalQuery(proposal_id=proposal_id, requester_id=auth.user_id)
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_planning_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(
                    data=ProposalResponse.from_dto(summary)
                ).model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/planning/proposals — Get proposal by trip               #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/trips/{trip_id}/planning/proposals",
    status_code=200,
    summary="Get the latest proposal for a trip",
    operation_id="getProposalByTrip",
    response_description="Latest proposal details.",
    responses={
        200: {"description": "Latest proposal found."},
        404: {"description": "No proposal found for this trip."},
        403: {"description": "Not the trip owner."},
    },
)
async def get_proposal_by_trip(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentGetProposalByTripHandler,
) -> Response:
    """Retrieve the latest proposal generated for a trip."""
    trace_id = get_request_id() or ""
    instance = f"{_TRIPS_BASE}/{trip_id}/planning/proposals"

    query = GetProposalByTripQuery(trip_id=trip_id, requester_id=auth.user_id)
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_planning_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(
                    data=ProposalResponse.from_dto(summary)
                ).model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /planning/proposals/{proposal_id}/accept — Accept proposal              #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/planning/proposals/{proposal_id}/accept",
    status_code=200,
    summary="Accept a generated proposal",
    operation_id="acceptProposal",
    response_description="Proposal successfully accepted.",
    responses={
        200: {"description": "Proposal accepted."},
        404: {"description": "Proposal not found."},
        403: {"description": "Not the proposal owner."},
        422: {"description": "Invalid status transition (e.g. not READY or EXPIRED)."},
    },
)
async def accept_proposal(
    proposal_id: str,
    auth: RequireAuthentication,
    handler: CurrentAcceptProposalHandler,
) -> Response:
    """Accept an generated travel proposal."""
    trace_id = get_request_id() or ""
    instance = f"{_PLANNING_BASE}/proposals/{proposal_id}/accept"

    command = AcceptProposalCommand(proposal_id=proposal_id, requester_id=auth.user_id)
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_planning_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(
                    data=ProposalResponse.from_dto(summary)
                ).model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /planning/proposals/{proposal_id}/reject — Reject proposal              #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/planning/proposals/{proposal_id}/reject",
    status_code=200,
    summary="Reject a generated proposal",
    operation_id="rejectProposal",
    response_description="Proposal successfully rejected.",
    responses={
        200: {"description": "Proposal rejected."},
        404: {"description": "Proposal not found."},
        403: {"description": "Not the proposal owner."},
        422: {"description": "Invalid status transition (e.g. not READY or EXPIRED)."},
    },
)
async def reject_proposal(
    proposal_id: str,
    auth: RequireAuthentication,
    handler: CurrentRejectProposalHandler,
) -> Response:
    """Reject a generated travel proposal."""
    trace_id = get_request_id() or ""
    instance = f"{_PLANNING_BASE}/proposals/{proposal_id}/reject"

    command = RejectProposalCommand(proposal_id=proposal_id, requester_id=auth.user_id)
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_planning_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(
                    data=ProposalResponse.from_dto(summary)
                ).model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /planning/proposals — List proposals                                     #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/planning/proposals",
    status_code=200,
    summary="List proposals for the authenticated user",
    operation_id="listProposals",
    response_description="Paginated list of proposals.",
    responses={
        200: {"description": "List of proposals retrieved."},
    },
)
async def list_proposals(
    auth: RequireAuthentication,
    handler: CurrentListProposalsHandler,
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Max proposals to return per page."),
    ] = 20,
    cursor: Annotated[
        str | None,
        Query(description="Opaque cursor token for next page."),
    ] = None,
) -> Response:
    """List proposals owned by the authenticated user with pagination."""
    trace_id = get_request_id() or ""
    instance = f"{_PLANNING_BASE}/proposals"

    query = ListProposalsQuery(
        owner_id=auth.user_id,
        requester_id=auth.user_id,
        limit=limit,
        cursor=cursor,
    )

    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_planning_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=page):
            return JSONResponse(
                status_code=200,
                content=DataEnvelope(
                    data=ProposalPageResponse.from_page_dto(page)
                ).model_dump(mode="json"),
                headers={"X-Request-ID": trace_id},
            )
