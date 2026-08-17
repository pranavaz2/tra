"""Sharing domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.shared.domain.events import DomainEvent


@dataclass(frozen=True, kw_only=True)
class TripInviteSent(DomainEvent):
    """Emitted when an invitation is sent to a prospective trip member."""

    collaboration_id: str
    trip_id: str
    invitation_id: str
    invitee_email: str
    role: str
    expires_at: datetime


@dataclass(frozen=True, kw_only=True)
class TripInviteAccepted(DomainEvent):
    """Emitted when an invited user accepts their invitation."""

    collaboration_id: str
    trip_id: str
    invitation_id: str
    member_id: str
    user_id: str
    role: str


@dataclass(frozen=True, kw_only=True)
class TripInviteDeclined(DomainEvent):
    """Emitted when an invited user declines their invitation."""

    collaboration_id: str
    trip_id: str
    invitation_id: str


@dataclass(frozen=True, kw_only=True)
class TripMemberRoleChanged(DomainEvent):
    """Emitted when a member's role is changed by the OWNER."""

    collaboration_id: str
    trip_id: str
    member_id: str
    old_role: str
    new_role: str


@dataclass(frozen=True, kw_only=True)
class TripMemberRemoved(DomainEvent):
    """Emitted when a member is removed from the collaboration."""

    collaboration_id: str
    trip_id: str
    member_id: str
    user_id: str


@dataclass(frozen=True, kw_only=True)
class TripSharedPublicly(DomainEvent):
    """Emitted when public sharing is enabled or the share token is rotated."""

    collaboration_id: str
    trip_id: str
    share_token: str


@dataclass(frozen=True, kw_only=True)
class TripShareRevoked(DomainEvent):
    """Emitted when public sharing is disabled."""

    collaboration_id: str
    trip_id: str
