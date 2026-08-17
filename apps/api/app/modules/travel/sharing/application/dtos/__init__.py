"""Sharing application DTOs and result type aliases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TypeAlias

from app.modules.travel.sharing.domain.entities.invitation import Invitation
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
from app.modules.travel.sharing.domain.entities.trip_member import TripMember
from app.shared.domain.result import Result


@dataclass(frozen=True)
class MemberSummary:
    """Summary DTO for a TripMember."""

    member_id: str
    user_id: str
    role: str
    joined_at: datetime

    @classmethod
    def from_entity(cls, member: TripMember) -> MemberSummary:
        return cls(
            member_id=str(member.entity_id),
            user_id=str(member.user_id),
            role=member.role.value,
            joined_at=member.joined_at,
        )


@dataclass(frozen=True)
class InvitationSummary:
    """Summary DTO for an Invitation."""

    invitation_id: str
    invitee_email: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime

    @classmethod
    def from_entity(cls, invitation: Invitation) -> InvitationSummary:
        return cls(
            invitation_id=str(invitation.entity_id),
            invitee_email=invitation.invitee_email,
            role=invitation.role.value,
            status=invitation.status.value,
            expires_at=invitation.expires_at,
            created_at=invitation.created_at,
        )


@dataclass(frozen=True)
class CollaborationSummary:
    """Summary DTO for a TripCollaboration."""

    collaboration_id: str
    trip_id: str
    owner_id: str
    member_count: int
    is_public: bool
    share_token: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_aggregate(cls, collab: TripCollaboration) -> CollaborationSummary:
        return cls(
            collaboration_id=str(collab.collaboration_id),
            trip_id=str(collab.trip_id),
            owner_id=str(collab.owner_id),
            member_count=collab.member_count,
            is_public=collab.is_public,
            share_token=str(collab.share_token) if collab.share_token else None,
            created_at=collab.created_at,
            updated_at=collab.updated_at,
        )


@dataclass(frozen=True)
class ShareTokenSummary:
    """Summary DTO returned when a share token is generated or rotated."""

    share_token: str
    is_public: bool


@dataclass(frozen=True)
class MemberListPage:
    """Cursor-paginated page of members."""

    items: tuple[MemberSummary, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


@dataclass(frozen=True)
class InvitationListPage:
    """Cursor-paginated page of invitations."""

    items: tuple[InvitationSummary, ...]
    next_cursor: str | None
    has_more: bool
    limit: int


# Result type aliases (Python 3.11 compatible TypeAlias with noqa UP040)
CreateCollaborationResult: TypeAlias = "Result[CollaborationSummary]"  # noqa: UP040
InviteMemberResult: TypeAlias = "Result[InvitationSummary]"  # noqa: UP040
AcceptInvitationResult: TypeAlias = "Result[MemberSummary]"  # noqa: UP040
DeclineInvitationResult: TypeAlias = "Result[None]"  # noqa: UP040
RevokeInvitationResult: TypeAlias = "Result[None]"  # noqa: UP040
ChangeMemberRoleResult: TypeAlias = "Result[MemberSummary]"  # noqa: UP040
RemoveMemberResult: TypeAlias = "Result[None]"  # noqa: UP040
EnablePublicSharingResult: TypeAlias = "Result[ShareTokenSummary]"  # noqa: UP040
DisablePublicSharingResult: TypeAlias = "Result[None]"  # noqa: UP040
RotateShareTokenResult: TypeAlias = "Result[ShareTokenSummary]"  # noqa: UP040
GetCollaborationResult: TypeAlias = "Result[CollaborationSummary]"  # noqa: UP040
ListMembersResult: TypeAlias = "Result[MemberListPage]"  # noqa: UP040
ListInvitationsResult: TypeAlias = "Result[InvitationListPage]"  # noqa: UP040
GetPublicTripResult: TypeAlias = "Result[CollaborationSummary]"  # noqa: UP040
