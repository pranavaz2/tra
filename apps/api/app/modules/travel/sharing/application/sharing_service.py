"""SharingService — orchestrates all use cases for TripCollaboration."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
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
    CollaborationSummary,
    CreateCollaborationResult,
    DeclineInvitationResult,
    DisablePublicSharingResult,
    EnablePublicSharingResult,
    GetCollaborationResult,
    GetPublicTripResult,
    InvitationListPage,
    InvitationSummary,
    InviteMemberResult,
    ListInvitationsResult,
    ListMembersResult,
    MemberListPage,
    MemberSummary,
    RemoveMemberResult,
    RevokeInvitationResult,
    RotateShareTokenResult,
    ShareTokenSummary,
)
from app.modules.travel.sharing.application.queries import (
    GetCollaborationQuery,
    GetPublicTripQuery,
    ListInvitationsQuery,
    ListMembersQuery,
)
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.errors import (
    CollaborationAlreadyExistsError,
    CollaborationNotFoundError,
    InvitationNotFoundError,
)
from app.modules.travel.sharing.domain.repositories.interfaces import (
    IInvitationRepository,
    ITripCollaborationRepository,
)
from app.modules.travel.sharing.domain.value_objects.collaboration_id import (
    CollaborationId,
)
from app.modules.travel.sharing.domain.value_objects.invitation_id import InvitationId
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider
from app.shared.infrastructure.clock import Clock

logger = logging.getLogger(__name__)


class SharingService:
    """Orchestrates all use cases for TripCollaboration and invitations."""

    def __init__(
        self,
        *,
        repository: ITripCollaborationRepository,
        invitation_repository: IInvitationRepository,
        trip_repository: ITripRepository,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._invitation_repository = invitation_repository
        self._trip_repository = trip_repository
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid_provider = uuid_provider
        self._clock = clock

    # ------------------------------------------------------------------ #
    # Collaboration bootstrap                                              #
    # ------------------------------------------------------------------ #

    async def create_collaboration(
        self, command: CreateCollaborationCommand
    ) -> CreateCollaborationResult:
        """Bootstrap a TripCollaboration for a trip."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            trip = await self._trip_repository.find_by_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load trip.", cause=exc))

        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))
        if trip.owner_id != requester_id:
            return Failure(ForbiddenError("You do not own this trip."))

        try:
            exists = await self._repository.exists_for_trip(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Database check failed.", cause=exc))

        if exists:
            return Failure(CollaborationAlreadyExistsError(str(trip_id)))

        collaboration_id = CollaborationId(value=self._uuid_provider.generate())
        owner_member_id = MemberId(value=self._uuid_provider.generate())
        collab = TripCollaboration.create(
            collaboration_id=collaboration_id,
            trip_id=trip_id,
            owner_id=requester_id,
            owner_member_id=owner_member_id,
        )

        try:
            async with self._uow:
                await self._repository.save(collab)
                await self._uow.commit()
        except Exception as exc:
            logger.error("Failed to save collaboration", extra={"reason": str(exc)})
            return Failure(InfrastructureError("Failed to save collaboration.", cause=exc))

        await self._publish(collab.pop_events(), context="create_collaboration")
        return Success(CollaborationSummary.from_aggregate(collab))

    # ------------------------------------------------------------------ #
    # Invitations                                                          #
    # ------------------------------------------------------------------ #

    async def invite_member(self, command: InviteMemberCommand) -> InviteMemberResult:
        """Invite a user by email to join the collaboration."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            role = MemberRole(command.role)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        invitation_id = InvitationId(value=self._uuid_provider.generate())

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                invitation = collab.invite_member(
                    invitation_id=invitation_id,
                    invitee_email=command.invitee_email,
                    role=role,
                    requester_id=requester_id,
                )
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to send invitation.", cause=exc))

        await self._publish(collab.pop_events(), context="invite_member")
        return Success(InvitationSummary.from_entity(invitation))

    async def accept_invitation(
        self, command: AcceptInvitationCommand
    ) -> AcceptInvitationResult:
        """Accept a pending invitation and join the collaboration."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            invitation_id = InvitationId.from_str(command.invitation_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        new_member_id = MemberId(value=self._uuid_provider.generate())

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                new_member = collab.accept_invitation(
                    invitation_id=invitation_id,
                    accepting_user_id=requester_id,
                    new_member_id=new_member_id,
                )
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to accept invitation.", cause=exc))

        await self._publish(collab.pop_events(), context="accept_invitation")
        return Success(MemberSummary.from_entity(new_member))

    async def decline_invitation(
        self, command: DeclineInvitationCommand
    ) -> DeclineInvitationResult:
        """Decline a pending invitation."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            invitation_id = InvitationId.from_str(command.invitation_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                collab.decline_invitation(invitation_id=invitation_id)
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to decline invitation.", cause=exc))

        await self._publish(collab.pop_events(), context="decline_invitation")
        return Success(None)

    async def revoke_invitation(
        self, command: RevokeInvitationCommand
    ) -> RevokeInvitationResult:
        """Revoke a pending invitation (OWNER only)."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            invitation_id = InvitationId.from_str(command.invitation_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                collab.revoke_invitation(
                    invitation_id=invitation_id,
                    requester_id=requester_id,
                )
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to revoke invitation.", cause=exc))

        await self._publish(collab.pop_events(), context="revoke_invitation")
        return Success(None)

    # ------------------------------------------------------------------ #
    # Members                                                              #
    # ------------------------------------------------------------------ #

    async def change_member_role(
        self, command: ChangeMemberRoleCommand
    ) -> ChangeMemberRoleResult:
        """Change the role of a member (OWNER only)."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            member_id = MemberId.from_str(command.member_id)
            new_role = MemberRole(command.new_role)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                collab.change_member_role(
                    member_id=member_id,
                    new_role=new_role,
                    requester_id=requester_id,
                )

                member = collab._find_member(member_id)

                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to change member role.", cause=exc))

        await self._publish(collab.pop_events(), context="change_member_role")
        return Success(MemberSummary.from_entity(member))  # type: ignore[arg-type]

    async def remove_member(self, command: RemoveMemberCommand) -> RemoveMemberResult:
        """Remove a member from the collaboration (OWNER only)."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
            member_id = MemberId.from_str(command.member_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                collab.remove_member(
                    member_id=member_id,
                    requester_id=requester_id,
                )
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to remove member.", cause=exc))

        await self._publish(collab.pop_events(), context="remove_member")
        return Success(None)

    # ------------------------------------------------------------------ #
    # Public sharing                                                       #
    # ------------------------------------------------------------------ #

    async def enable_public_sharing(
        self, command: EnablePublicSharingCommand
    ) -> EnablePublicSharingResult:
        """Enable public sharing and return the share token."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                token = collab.enable_public_sharing(requester_id=requester_id)
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to enable public sharing.", cause=exc))

        await self._publish(collab.pop_events(), context="enable_public_sharing")
        return Success(ShareTokenSummary(share_token=str(token), is_public=True))

    async def disable_public_sharing(
        self, command: DisablePublicSharingCommand
    ) -> DisablePublicSharingResult:
        """Disable public sharing and clear the share token."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                collab.disable_public_sharing(requester_id=requester_id)
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to disable public sharing.", cause=exc))

        await self._publish(collab.pop_events(), context="disable_public_sharing")
        return Success(None)

    async def rotate_share_token(
        self, command: RotateShareTokenCommand
    ) -> RotateShareTokenResult:
        """Rotate the share token, invalidating the previous one."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                collab = await self._repository.find_by_trip_id(trip_id)
                if collab is None or collab.is_deleted:
                    return Failure(CollaborationNotFoundError(str(trip_id)))

                token = collab.rotate_share_token(requester_id=requester_id)
                await self._repository.save(collab)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to rotate share token.", cause=exc))

        await self._publish(collab.pop_events(), context="rotate_share_token")
        return Success(ShareTokenSummary(share_token=str(token), is_public=True))

    # ------------------------------------------------------------------ #
    # Queries                                                              #
    # ------------------------------------------------------------------ #

    async def get_collaboration(
        self, query: GetCollaborationQuery
    ) -> GetCollaborationResult:
        """Get collaboration details for a trip."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            collab = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collaboration.", cause=exc))

        if collab is None or collab.is_deleted:
            return Failure(CollaborationNotFoundError(str(trip_id)))

        # Any member can view the collaboration
        if not any(str(m.user_id) == str(requester_id) for m in collab.members):
            return Failure(ForbiddenError("You are not a member of this collaboration."))

        return Success(CollaborationSummary.from_aggregate(collab))

    async def list_members(self, query: ListMembersQuery) -> ListMembersResult:
        """List members with cursor-based pagination."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            collab = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collaboration.", cause=exc))

        if collab is None or collab.is_deleted:
            return Failure(CollaborationNotFoundError(str(trip_id)))

        if not any(str(m.user_id) == str(requester_id) for m in collab.members):
            return Failure(ForbiddenError("You are not a member of this collaboration."))

        members = sorted(collab.members, key=lambda m: (m.joined_at, str(m.entity_id)))

        after_id: str | None = None
        if query.cursor is not None:
            try:
                after_id = decode_cursor(query.cursor)
            except Exception:
                return Failure(
                    ValidationError(
                        "Invalid pagination cursor.",
                        field="cursor",
                        value=query.cursor,
                    )
                )

        if after_id is not None:
            cursor_member = next(
                (m for m in members if str(m.entity_id) == after_id), None
            )
            if cursor_member is not None:
                members = [
                    m
                    for m in members
                    if (m.joined_at, str(m.entity_id))
                    > (cursor_member.joined_at, str(cursor_member.entity_id))
                ]

        has_more = len(members) > query.limit
        if has_more:
            members = members[: query.limit]

        next_cursor: str | None = None
        if has_more and members:
            next_cursor = encode_cursor(str(members[-1].entity_id))

        return Success(
            MemberListPage(
                items=tuple(MemberSummary.from_entity(m) for m in members),
                next_cursor=next_cursor,
                has_more=has_more,
                limit=query.limit,
            )
        )

    async def list_invitations(
        self, query: ListInvitationsQuery
    ) -> ListInvitationsResult:
        """List invitations with cursor-based pagination (OWNER only)."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            collab = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collaboration.", cause=exc))

        if collab is None or collab.is_deleted:
            return Failure(CollaborationNotFoundError(str(trip_id)))

        if requester_id != collab.owner_id:
            return Failure(ForbiddenError("Only the trip owner can view invitations."))

        invitations = sorted(
            collab.invitations,
            key=lambda i: (i.created_at, str(i.entity_id)),
            reverse=True,
        )

        after_id: str | None = None
        if query.cursor is not None:
            try:
                after_id = decode_cursor(query.cursor)
            except Exception:
                return Failure(
                    ValidationError(
                        "Invalid pagination cursor.",
                        field="cursor",
                        value=query.cursor,
                    )
                )

        if after_id is not None:
            cursor_inv = next(
                (i for i in invitations if str(i.entity_id) == after_id), None
            )
            if cursor_inv is not None:
                invitations = [
                    i
                    for i in invitations
                    if (i.created_at, str(i.entity_id))
                    < (cursor_inv.created_at, str(cursor_inv.entity_id))
                ]

        has_more = len(invitations) > query.limit
        if has_more:
            invitations = invitations[: query.limit]

        next_cursor: str | None = None
        if has_more and invitations:
            next_cursor = encode_cursor(str(invitations[-1].entity_id))

        return Success(
            InvitationListPage(
                items=tuple(InvitationSummary.from_entity(i) for i in invitations),
                next_cursor=next_cursor,
                has_more=has_more,
                limit=query.limit,
            )
        )

    async def get_public_trip(
        self, query: GetPublicTripQuery
    ) -> GetPublicTripResult:
        """Get a publicly shared collaboration by share token (no auth required)."""
        try:
            invitation = await self._invitation_repository.find_by_token(query.token)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to look up share token.", cause=exc))

        # The IInvitationRepository.find_by_token is used here to locate
        # the collaboration via the token. The actual collaboration lookup is
        # done via the collaboration repository using the trip's collaboration record.
        # For the public share token, we use the share_token field on the
        # TripCollaboration aggregate — so we delegate to the collaboration repository.
        try:
            collab = await self._repository.find_by_share_token(query.token)
        except AttributeError:
            # Fallback: find via invitation token if repository does not support
            # find_by_share_token. This path is only hit by older repo implementations.
            if invitation is None:
                return Failure(CollaborationNotFoundError(query.token))
            return Failure(
                InfrastructureError("Repository does not support find_by_share_token.")
            )
        except Exception as exc:
            return Failure(InfrastructureError("Failed to look up collaboration.", cause=exc))

        if collab is None or collab.is_deleted:
            return Failure(CollaborationNotFoundError(query.token))

        if not collab.is_public:
            return Failure(CollaborationNotFoundError(query.token))

        return Success(CollaborationSummary.from_aggregate(collab))

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _publish(self, events: Sequence[DomainEvent], *, context: str) -> None:
        """Publish domain events safely."""
        if not events:
            return
        try:
            await self._event_publisher.publish(events)
        except Exception as exc:
            logger.error(
                "Event publication failed",
                extra={
                    "context": context,
                    "event_count": len(events),
                    "reason": str(exc),
                },
            )
