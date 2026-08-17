"""Sharing CQRS command and query handlers."""

from __future__ import annotations

import logging

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
from app.modules.travel.sharing.application.dtos import (
    AcceptInvitationResult,
    ChangeMemberRoleResult,
    CreateCollaborationResult,
    DeclineInvitationResult,
    DisablePublicSharingResult,
    EnablePublicSharingResult,
    GetCollaborationResult,
    GetPublicTripResult,
    InviteMemberResult,
    ListInvitationsResult,
    ListMembersResult,
    RemoveMemberResult,
    RevokeInvitationResult,
    RotateShareTokenResult,
)
from app.modules.travel.sharing.application.queries import (
    GetCollaborationQuery,
    GetPublicTripQuery,
    ListInvitationsQuery,
    ListMembersQuery,
)
from app.modules.travel.sharing.application.sharing_service import SharingService

logger = logging.getLogger(__name__)


class CreateCollaborationHandler:
    """CQRS handler for CreateCollaborationCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: CreateCollaborationCommand) -> CreateCollaborationResult:
        logger.debug(
            "Handling CreateCollaborationCommand",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )
        return await self._service.create_collaboration(command)


class InviteMemberHandler:
    """CQRS handler for InviteMemberCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: InviteMemberCommand) -> InviteMemberResult:
        logger.debug(
            "Handling InviteMemberCommand",
            extra={"trip_id": command.trip_id, "invitee_email": command.invitee_email},
        )
        return await self._service.invite_member(command)


class AcceptInvitationHandler:
    """CQRS handler for AcceptInvitationCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: AcceptInvitationCommand) -> AcceptInvitationResult:
        logger.debug(
            "Handling AcceptInvitationCommand",
            extra={"invitation_id": command.invitation_id},
        )
        return await self._service.accept_invitation(command)


class DeclineInvitationHandler:
    """CQRS handler for DeclineInvitationCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: DeclineInvitationCommand) -> DeclineInvitationResult:
        logger.debug(
            "Handling DeclineInvitationCommand",
            extra={"invitation_id": command.invitation_id},
        )
        return await self._service.decline_invitation(command)


class RevokeInvitationHandler:
    """CQRS handler for RevokeInvitationCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: RevokeInvitationCommand) -> RevokeInvitationResult:
        logger.debug(
            "Handling RevokeInvitationCommand",
            extra={"invitation_id": command.invitation_id},
        )
        return await self._service.revoke_invitation(command)


class ChangeMemberRoleHandler:
    """CQRS handler for ChangeMemberRoleCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: ChangeMemberRoleCommand) -> ChangeMemberRoleResult:
        logger.debug(
            "Handling ChangeMemberRoleCommand",
            extra={"trip_id": command.trip_id, "member_id": command.member_id},
        )
        return await self._service.change_member_role(command)


class RemoveMemberHandler:
    """CQRS handler for RemoveMemberCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: RemoveMemberCommand) -> RemoveMemberResult:
        logger.debug(
            "Handling RemoveMemberCommand",
            extra={"trip_id": command.trip_id, "member_id": command.member_id},
        )
        return await self._service.remove_member(command)


class EnablePublicSharingHandler:
    """CQRS handler for EnablePublicSharingCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: EnablePublicSharingCommand) -> EnablePublicSharingResult:
        logger.debug(
            "Handling EnablePublicSharingCommand",
            extra={"trip_id": command.trip_id},
        )
        return await self._service.enable_public_sharing(command)


class DisablePublicSharingHandler:
    """CQRS handler for DisablePublicSharingCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: DisablePublicSharingCommand) -> DisablePublicSharingResult:
        logger.debug(
            "Handling DisablePublicSharingCommand",
            extra={"trip_id": command.trip_id},
        )
        return await self._service.disable_public_sharing(command)


class RotateShareTokenHandler:
    """CQRS handler for RotateShareTokenCommand."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, command: RotateShareTokenCommand) -> RotateShareTokenResult:
        logger.debug(
            "Handling RotateShareTokenCommand",
            extra={"trip_id": command.trip_id},
        )
        return await self._service.rotate_share_token(command)


class GetCollaborationHandler:
    """CQRS handler for GetCollaborationQuery."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, query: GetCollaborationQuery) -> GetCollaborationResult:
        logger.debug(
            "Handling GetCollaborationQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.get_collaboration(query)


class ListMembersHandler:
    """CQRS handler for ListMembersQuery."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, query: ListMembersQuery) -> ListMembersResult:
        logger.debug(
            "Handling ListMembersQuery",
            extra={"trip_id": query.trip_id},
        )
        return await self._service.list_members(query)


class ListInvitationsHandler:
    """CQRS handler for ListInvitationsQuery."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, query: ListInvitationsQuery) -> ListInvitationsResult:
        logger.debug(
            "Handling ListInvitationsQuery",
            extra={"trip_id": query.trip_id},
        )
        return await self._service.list_invitations(query)


class GetPublicTripHandler:
    """CQRS handler for GetPublicTripQuery."""

    def __init__(self, service: SharingService) -> None:
        self._service = service

    async def handle(self, query: GetPublicTripQuery) -> GetPublicTripResult:
        logger.debug(
            "Handling GetPublicTripQuery",
            extra={"token": query.token[:8] + "..."},  # truncate for log safety
        )
        return await self._service.get_public_trip(query)
