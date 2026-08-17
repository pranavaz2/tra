"""Sharing application commands."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CreateCollaborationCommand:
    """Command to bootstrap a collaboration for a newly created trip."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class InviteMemberCommand:
    """Command to invite a user to join a trip collaboration."""

    trip_id: str
    invitee_email: str
    role: str
    requester_id: str


@dataclass(frozen=True)
class AcceptInvitationCommand:
    """Command to accept a pending invitation."""

    trip_id: str
    invitation_id: str
    requester_id: str


@dataclass(frozen=True)
class DeclineInvitationCommand:
    """Command to decline a pending invitation."""

    trip_id: str
    invitation_id: str
    requester_id: str


@dataclass(frozen=True)
class RevokeInvitationCommand:
    """Command to revoke a pending invitation (OWNER only)."""

    trip_id: str
    invitation_id: str
    requester_id: str


@dataclass(frozen=True)
class ChangeMemberRoleCommand:
    """Command to change the role of an existing member (OWNER only)."""

    trip_id: str
    member_id: str
    new_role: str
    requester_id: str


@dataclass(frozen=True)
class RemoveMemberCommand:
    """Command to remove a member from the collaboration (OWNER only)."""

    trip_id: str
    member_id: str
    requester_id: str


@dataclass(frozen=True)
class EnablePublicSharingCommand:
    """Command to enable public (read-only) sharing via a share token."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class DisablePublicSharingCommand:
    """Command to disable public sharing and clear the share token."""

    trip_id: str
    requester_id: str


@dataclass(frozen=True)
class RotateShareTokenCommand:
    """Command to rotate the public share token, invalidating the previous one."""

    trip_id: str
    requester_id: str
