"""Sharing Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, status
from fastapi.responses import JSONResponse, Response

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.sharing.application.commands import (
    AcceptInvitationCommand,
    ChangeMemberRoleCommand,
    CreateCollaborationCommand,
    DeclineInvitationCommand,
    DisablePublicSharingCommand,
    EnablePublicSharingCommand,
    InviteMemberCommand,
    RemoveMemberCommand,
    RevokeInvitationCommand,
    RotateShareTokenCommand,
)
from app.modules.travel.sharing.application.queries import (
    GetCollaborationQuery,
    GetPublicTripQuery,
    ListInvitationsQuery,
    ListMembersQuery,
)
from app.modules.travel.sharing.infrastructure.dependencies import (
    CurrentAcceptInvitationHandler,
    CurrentChangeMemberRoleHandler,
    CurrentCreateCollaborationHandler,
    CurrentDeclineInvitationHandler,
    CurrentDisablePublicSharingHandler,
    CurrentEnablePublicSharingHandler,
    CurrentGetCollaborationHandler,
    CurrentGetPublicTripHandler,
    CurrentInviteMemberHandler,
    CurrentListInvitationsHandler,
    CurrentListMembersHandler,
    CurrentRemoveMemberHandler,
    CurrentRevokeInvitationHandler,
    CurrentRotateShareTokenHandler,
)
from app.modules.travel.sharing.presentation.error_responses import map_sharing_failure
from app.modules.travel.sharing.presentation.schemas import (
    ChangeMemberRoleRequest,
    CollaborationResponse,
    DataEnvelope,
    InvitationListResponse,
    InvitationResponse,
    InviteMemberRequest,
    MemberListResponse,
    MemberResponse,
    PublicSharingRequest,
    ShareTokenResponse,
)
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["Collaboration & Sharing"])


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/collaboration — Bootstrap collaboration                  #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/collaboration",
    response_model=DataEnvelope[CollaborationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create trip collaboration",
    operation_id="createCollaboration",
)
async def create_collaboration(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentCreateCollaborationHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration"

    command = CreateCollaborationCommand(
        trip_id=trip_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=CollaborationResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/collaboration — Get collaboration details                 #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/collaboration",
    response_model=DataEnvelope[CollaborationResponse],
    summary="Get trip collaboration",
    operation_id="getCollaboration",
)
async def get_collaboration(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentGetCollaborationHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration"

    query = GetCollaborationQuery(trip_id=trip_id, requester_id=str(auth.user_id))
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=CollaborationResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/collaboration/members — List members                      #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/collaboration/members",
    response_model=DataEnvelope[MemberListResponse],
    summary="List collaboration members",
    operation_id="listCollaborationMembers",
)
async def list_members(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentListMembersHandler,
    limit: int = Query(20, ge=1, le=100, description="Page limit."),
    cursor: str | None = Query(None, description="Keyset pagination cursor."),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/members"

    query = ListMembersQuery(
        trip_id=trip_id,
        requester_id=str(auth.user_id),
        limit=limit,
        cursor=cursor,
    )
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=page):
            envelope = DataEnvelope(data=MemberListResponse.model_validate(page))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/collaboration/invitations — Send invitation               #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/collaboration/invitations",
    response_model=DataEnvelope[InvitationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member",
    operation_id="inviteMember",
)
async def invite_member(
    trip_id: str,
    body: InviteMemberRequest,
    auth: RequireAuthentication,
    handler: CurrentInviteMemberHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/invitations"

    command = InviteMemberCommand(
        trip_id=trip_id,
        invitee_email=str(body.invitee_email),
        role=body.role,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=InvitationResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/{trip_id}/collaboration/invitations — List invitations               #
# ──────────────────────────────────────────────────────────────────────────── #


@router.get(
    "/{trip_id}/collaboration/invitations",
    response_model=DataEnvelope[InvitationListResponse],
    summary="List collaboration invitations",
    operation_id="listCollaborationInvitations",
)
async def list_invitations(
    trip_id: str,
    auth: RequireAuthentication,
    handler: CurrentListInvitationsHandler,
    limit: int = Query(20, ge=1, le=100, description="Page limit."),
    cursor: str | None = Query(None, description="Keyset pagination cursor."),
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/invitations"

    query = ListInvitationsQuery(
        trip_id=trip_id,
        requester_id=str(auth.user_id),
        limit=limit,
        cursor=cursor,
    )
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=page):
            envelope = DataEnvelope(data=InvitationListResponse.model_validate(page))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/collaboration/invitations/{invitation_id}/accept          #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/collaboration/invitations/{invitation_id}/accept",
    response_model=DataEnvelope[MemberResponse],
    summary="Accept an invitation",
    operation_id="acceptInvitation",
)
async def accept_invitation(
    trip_id: str,
    invitation_id: str,
    auth: RequireAuthentication,
    handler: CurrentAcceptInvitationHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/invitations/{invitation_id}/accept"

    command = AcceptInvitationCommand(
        trip_id=trip_id,
        invitation_id=invitation_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=member):
            envelope = DataEnvelope(data=MemberResponse.model_validate(member))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# POST /trips/{trip_id}/collaboration/invitations/{invitation_id}/decline         #
# ──────────────────────────────────────────────────────────────────────────── #


@router.post(
    "/{trip_id}/collaboration/invitations/{invitation_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Decline an invitation",
    operation_id="declineInvitation",
)
async def decline_invitation(
    trip_id: str,
    invitation_id: str,
    auth: RequireAuthentication,
    handler: CurrentDeclineInvitationHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/invitations/{invitation_id}/decline"

    command = DeclineInvitationCommand(
        trip_id=trip_id,
        invitation_id=invitation_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success():
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id}/collaboration/invitations/{invitation_id} — Revoke      #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}/collaboration/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke a pending invitation",
    operation_id="revokeInvitation",
)
async def revoke_invitation(
    trip_id: str,
    invitation_id: str,
    auth: RequireAuthentication,
    handler: CurrentRevokeInvitationHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/invitations/{invitation_id}"

    command = RevokeInvitationCommand(
        trip_id=trip_id,
        invitation_id=invitation_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success():
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/collaboration/members/{member_id} — Change role         #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/collaboration/members/{member_id}",
    response_model=DataEnvelope[MemberResponse],
    summary="Change a member's role",
    operation_id="changeMemberRole",
)
async def change_member_role(
    trip_id: str,
    member_id: str,
    body: ChangeMemberRoleRequest,
    auth: RequireAuthentication,
    handler: CurrentChangeMemberRoleHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/members/{member_id}"

    command = ChangeMemberRoleCommand(
        trip_id=trip_id,
        member_id=member_id,
        new_role=body.role,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=member):
            envelope = DataEnvelope(data=MemberResponse.model_validate(member))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# DELETE /trips/{trip_id}/collaboration/members/{member_id} — Remove member      #
# ──────────────────────────────────────────────────────────────────────────── #


@router.delete(
    "/{trip_id}/collaboration/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from the collaboration",
    operation_id="removeMember",
)
async def remove_member(
    trip_id: str,
    member_id: str,
    auth: RequireAuthentication,
    handler: CurrentRemoveMemberHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/members/{member_id}"

    command = RemoveMemberCommand(
        trip_id=trip_id,
        member_id=member_id,
        requester_id=str(auth.user_id),
    )
    result = await handler.handle(command)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success():
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# PATCH /trips/{trip_id}/collaboration/sharing — Enable/disable/rotate token     #
# ──────────────────────────────────────────────────────────────────────────── #


@router.patch(
    "/{trip_id}/collaboration/sharing",
    response_model=DataEnvelope[ShareTokenResponse],
    summary="Toggle or rotate public sharing",
    operation_id="updatePublicSharing",
)
async def update_public_sharing(
    trip_id: str,
    body: PublicSharingRequest,
    auth: RequireAuthentication,
    enable_handler: CurrentEnablePublicSharingHandler,
    disable_handler: CurrentDisablePublicSharingHandler,
    rotate_handler: CurrentRotateShareTokenHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/collaboration/sharing"
    requester_id = str(auth.user_id)

    match body.action:
        case "enable":
            command = EnablePublicSharingCommand(trip_id=trip_id, requester_id=requester_id)
            result = await enable_handler.handle(command)
        case "disable":
            command_d = DisablePublicSharingCommand(trip_id=trip_id, requester_id=requester_id)
            result_d = await disable_handler.handle(command_d)
            if isinstance(result_d, Failure):
                return map_sharing_failure(result_d.error, trace_id=trace_id, instance=instance)
            return Response(
                status_code=status.HTTP_204_NO_CONTENT,
                headers={"X-Request-ID": trace_id},
            )
        case "rotate":
            command_r = RotateShareTokenCommand(trip_id=trip_id, requester_id=requester_id)
            result = await rotate_handler.handle(command_r)
        case _:
            # This branch is unreachable — Pydantic validates the Literal
            result = Failure(  # type: ignore[assignment]
                __import__(
                    "app.shared.domain.errors", fromlist=["ValidationError"]
                ).ValidationError("Unknown action.")
            )

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=token_summary):
            envelope = DataEnvelope(
                data=ShareTokenResponse.model_validate(token_summary)
            )
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )


# ──────────────────────────────────────────────────────────────────────────── #
# GET /trips/public/{token} — Get publicly shared trip (no auth required)        #
# ──────────────────────────────────────────────────────────────────────────── #


public_router = APIRouter(prefix="/trips", tags=["Collaboration & Sharing"])


@public_router.get(
    "/public/{token}",
    response_model=DataEnvelope[CollaborationResponse],
    summary="Get a publicly shared trip by share token",
    operation_id="getPublicTrip",
)
async def get_public_trip(
    token: str,
    handler: CurrentGetPublicTripHandler,
) -> Response:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/public/{token}"

    query = GetPublicTripQuery(token=token)
    result = await handler.handle(query)

    match result:
        case Failure(error=err):
            return map_sharing_failure(err, trace_id=trace_id, instance=instance)
        case Success(value=summary):
            envelope = DataEnvelope(data=CollaborationResponse.model_validate(summary))
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=envelope.model_dump(mode="json", by_alias=True),
                headers={"X-Request-ID": trace_id},
            )
