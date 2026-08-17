"""TripCollaboration aggregate root."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.sharing.domain.entities.invitation import Invitation
from app.modules.travel.sharing.domain.entities.trip_member import TripMember
from app.modules.travel.sharing.domain.enums.invitation_status import InvitationStatus
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.errors import (
    CannotChangeOwnerRoleError,
    CannotRemoveOwnerError,
    CollaborationAlreadyLockedError,
    InvitationAlreadyExistsError,
    InvitationNotFoundError,
    InvalidInvitationStatusError,
    MemberNotFoundError,
    OnlyOwnerCanModifyError,
    PublicSharingNotEnabledError,
)
from app.modules.travel.sharing.domain.events.sharing_events import (
    TripInviteAccepted,
    TripInviteDeclined,
    TripInviteSent,
    TripMemberRemoved,
    TripMemberRoleChanged,
    TripShareRevoked,
    TripSharedPublicly,
)
from app.modules.travel.sharing.domain.value_objects.collaboration_id import (
    CollaborationId,
)
from app.modules.travel.sharing.domain.value_objects.invitation_id import InvitationId
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.modules.travel.sharing.domain.value_objects.share_token import ShareToken
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.aggregate import AggregateRoot

# Invitations expire after 7 days by default
_INVITATION_TTL_DAYS = 7


@dataclass(kw_only=True, eq=False)
class TripCollaboration(AggregateRoot[CollaborationId]):
    """
    TripCollaboration aggregate root.

    Manages membership, invitations, and public-sharing settings for a
    single trip. Enforces all collaboration invariants:

      - Exactly one OWNER at all times.
      - The OWNER cannot leave or have their role changed.
      - Only the OWNER can invite, revoke invitations, or change roles.
      - An invitation email cannot be pending twice simultaneously.
      - Public share tokens are only valid while is_public is True.
    """

    trip_id: TripId
    owner_id: UserId
    members: list[TripMember] = field(default_factory=list)
    invitations: list[Invitation] = field(default_factory=list)
    is_public: bool = False
    share_token: ShareToken | None = None
    version: int = 1
    deleted_at: datetime | None = None

    # ------------------------------------------------------------------ #
    # Factory                                                              #
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        *,
        collaboration_id: CollaborationId,
        trip_id: TripId,
        owner_id: UserId,
        owner_member_id: MemberId,
    ) -> TripCollaboration:
        """
        Bootstrap a new TripCollaboration with the OWNER as the first member.
        """
        now = datetime.now(UTC)
        owner_member = TripMember(
            entity_id=owner_member_id,
            user_id=owner_id,
            role=MemberRole.OWNER,
            joined_at=now,
        )

        collab = cls(
            entity_id=collaboration_id,
            trip_id=trip_id,
            owner_id=owner_id,
            members=[owner_member],
            version=1,
        )

        return collab

    # ------------------------------------------------------------------ #
    # Identity shortcut                                                    #
    # ------------------------------------------------------------------ #

    @property
    def collaboration_id(self) -> CollaborationId:
        """Alias for entity_id with the concrete CollaborationId type."""
        return self.entity_id

    # ------------------------------------------------------------------ #
    # Derived state                                                        #
    # ------------------------------------------------------------------ #

    @property
    def is_deleted(self) -> bool:
        """True if this collaboration has been soft-deleted."""
        return self.deleted_at is not None

    @property
    def member_count(self) -> int:
        """Number of active members in this collaboration."""
        return len(self.members)

    def _find_member(self, member_id: MemberId) -> TripMember | None:
        return next((m for m in self.members if m.entity_id == member_id), None)

    def _find_invitation(self, invitation_id: InvitationId) -> Invitation | None:
        return next((i for i in self.invitations if i.entity_id == invitation_id), None)

    def _find_owner_member(self) -> TripMember | None:
        return next((m for m in self.members if m.role == MemberRole.OWNER), None)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _guard_not_deleted(self) -> None:
        if self.is_deleted:
            raise CollaborationAlreadyLockedError()

    def _mutate(self) -> None:
        """Increment version and touch audit timestamp."""
        self.version += 1
        self.touch()

    # ------------------------------------------------------------------ #
    # Mutations — Invitations                                              #
    # ------------------------------------------------------------------ #

    def invite_member(
        self,
        *,
        invitation_id: InvitationId,
        invitee_email: str,
        role: MemberRole,
        requester_id: UserId,
    ) -> Invitation:
        """
        Send an invitation to a new member.

        Rules:
          - Only the OWNER can invite.
          - Role cannot be OWNER.
          - Same email cannot have a PENDING invitation twice.
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("invite members")

        if role == MemberRole.OWNER:
            raise CannotChangeOwnerRoleError(
                "Cannot invite a member with the OWNER role."
            )

        normalized_email = invitee_email.strip().lower()
        pending = [
            i
            for i in self.invitations
            if i.invitee_email == normalized_email
            and i.status == InvitationStatus.PENDING
        ]
        if pending:
            raise InvitationAlreadyExistsError(normalized_email)

        now = datetime.now(UTC)
        invitation = Invitation(
            entity_id=invitation_id,
            invitee_email=normalized_email,
            role=role,
            status=InvitationStatus.PENDING,
            token=ShareToken.generate().value,
            expires_at=now + timedelta(days=_INVITATION_TTL_DAYS),
        )

        self.invitations.append(invitation)
        self._mutate()

        self.push_event(
            TripInviteSent(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                invitation_id=str(invitation_id),
                invitee_email=normalized_email,
                role=role.value,
                expires_at=invitation.expires_at,
            )
        )

        return invitation

    def accept_invitation(
        self,
        *,
        invitation_id: InvitationId,
        accepting_user_id: UserId,
        new_member_id: MemberId,
    ) -> TripMember:
        """
        Accept a pending invitation and add the user as a member.

        Rules:
          - Invitation must be PENDING.
          - Invitation must not be expired.
        """
        self._guard_not_deleted()

        invitation = self._find_invitation(invitation_id)
        if invitation is None:
            raise InvitationNotFoundError(str(invitation_id))

        if invitation.status != InvitationStatus.PENDING:
            raise InvalidInvitationStatusError(
                invitation_id=str(invitation_id),
                current_status=invitation.status.value,
                expected_status=InvitationStatus.PENDING.value,
            )

        now = datetime.now(UTC)
        if now > invitation.expires_at:
            invitation.status = InvitationStatus.EXPIRED
            self._mutate()
            raise InvalidInvitationStatusError(
                invitation_id=str(invitation_id),
                current_status=InvitationStatus.EXPIRED.value,
                expected_status=InvitationStatus.PENDING.value,
            )

        invitation.status = InvitationStatus.ACCEPTED
        invitation.touch()

        new_member = TripMember(
            entity_id=new_member_id,
            user_id=accepting_user_id,
            role=invitation.role,
            joined_at=now,
        )
        self.members.append(new_member)
        self._mutate()

        self.push_event(
            TripInviteAccepted(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                invitation_id=str(invitation_id),
                member_id=str(new_member_id),
                user_id=str(accepting_user_id),
                role=new_member.role.value,
            )
        )

        return new_member

    def decline_invitation(
        self,
        *,
        invitation_id: InvitationId,
    ) -> None:
        """
        Decline a pending invitation.

        Rules:
          - Invitation must be PENDING.
        """
        self._guard_not_deleted()

        invitation = self._find_invitation(invitation_id)
        if invitation is None:
            raise InvitationNotFoundError(str(invitation_id))

        if invitation.status != InvitationStatus.PENDING:
            raise InvalidInvitationStatusError(
                invitation_id=str(invitation_id),
                current_status=invitation.status.value,
                expected_status=InvitationStatus.PENDING.value,
            )

        invitation.status = InvitationStatus.DECLINED
        invitation.touch()
        self._mutate()

        self.push_event(
            TripInviteDeclined(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                invitation_id=str(invitation_id),
            )
        )

    def revoke_invitation(
        self,
        *,
        invitation_id: InvitationId,
        requester_id: UserId,
    ) -> None:
        """
        Revoke a pending invitation.

        Rules:
          - Only the OWNER can revoke.
          - Invitation must be PENDING.
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("revoke invitations")

        invitation = self._find_invitation(invitation_id)
        if invitation is None:
            raise InvitationNotFoundError(str(invitation_id))

        if invitation.status != InvitationStatus.PENDING:
            raise InvalidInvitationStatusError(
                invitation_id=str(invitation_id),
                current_status=invitation.status.value,
                expected_status=InvitationStatus.PENDING.value,
            )

        invitation.status = InvitationStatus.REVOKED
        invitation.touch()
        self._mutate()

    # ------------------------------------------------------------------ #
    # Mutations — Members                                                  #
    # ------------------------------------------------------------------ #

    def change_member_role(
        self,
        *,
        member_id: MemberId,
        new_role: MemberRole,
        requester_id: UserId,
    ) -> None:
        """
        Change the role of an existing member.

        Rules:
          - Only the OWNER can change roles.
          - The OWNER's own role cannot be changed.
          - The new role cannot be OWNER (ownership transfer is not supported).
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("change member roles")

        member = self._find_member(member_id)
        if member is None:
            raise MemberNotFoundError(str(member_id))

        if member.role == MemberRole.OWNER:
            raise CannotChangeOwnerRoleError(
                "The OWNER's role cannot be changed."
            )

        if new_role == MemberRole.OWNER:
            raise CannotChangeOwnerRoleError(
                "Cannot promote a member to OWNER. Ownership transfer is not supported."
            )

        old_role = member.role
        member.role = new_role
        member.touch()
        self._mutate()

        self.push_event(
            TripMemberRoleChanged(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                member_id=str(member_id),
                old_role=old_role.value,
                new_role=new_role.value,
            )
        )

    def remove_member(
        self,
        *,
        member_id: MemberId,
        requester_id: UserId,
    ) -> None:
        """
        Remove a member from the collaboration.

        Rules:
          - Only the OWNER can remove members.
          - The OWNER cannot remove themselves.
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("remove members")

        member = self._find_member(member_id)
        if member is None:
            raise MemberNotFoundError(str(member_id))

        if member.role == MemberRole.OWNER:
            raise CannotRemoveOwnerError()

        self.members.remove(member)
        self._mutate()

        self.push_event(
            TripMemberRemoved(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                member_id=str(member_id),
                user_id=str(member.user_id),
            )
        )

    # ------------------------------------------------------------------ #
    # Mutations — Public Sharing                                           #
    # ------------------------------------------------------------------ #

    def enable_public_sharing(self, *, requester_id: UserId) -> ShareToken:
        """
        Enable public (read-only) access to this trip via a share token.

        Rules:
          - Only the OWNER can enable public sharing.
          - Generates a new token each time it is called.
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("enable public sharing")

        token = ShareToken.generate()
        self.is_public = True
        self.share_token = token
        self._mutate()

        self.push_event(
            TripSharedPublicly(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                share_token=token.value,
            )
        )

        return token

    def disable_public_sharing(self, *, requester_id: UserId) -> None:
        """
        Disable public access and clear the share token.

        Rules:
          - Only the OWNER can disable public sharing.
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("disable public sharing")

        self.is_public = False
        self.share_token = None
        self._mutate()

        self.push_event(
            TripShareRevoked(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
            )
        )

    def rotate_share_token(self, *, requester_id: UserId) -> ShareToken:
        """
        Generate a new share token, invalidating the previous one.

        Rules:
          - Only the OWNER can rotate the token.
          - Public sharing must already be enabled.
        """
        self._guard_not_deleted()

        if requester_id != self.owner_id:
            raise OnlyOwnerCanModifyError("rotate the share token")

        if not self.is_public:
            raise PublicSharingNotEnabledError()

        token = ShareToken.generate()
        self.share_token = token
        self._mutate()

        self.push_event(
            TripSharedPublicly(
                aggregate_id=str(self.collaboration_id),
                collaboration_id=str(self.collaboration_id),
                trip_id=str(self.trip_id),
                share_token=token.value,
            )
        )

        return token

    def delete(self) -> None:
        """Soft-delete the collaboration aggregate."""
        if self.is_deleted:
            raise CollaborationAlreadyLockedError()
        self.deleted_at = datetime.now(UTC)
        self._mutate()
