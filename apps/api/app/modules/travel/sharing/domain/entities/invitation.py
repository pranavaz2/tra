"""Invitation entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.modules.travel.sharing.domain.enums.invitation_status import InvitationStatus
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.value_objects.invitation_id import InvitationId
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class Invitation(Entity[InvitationId]):
    """
    Invitation entity.

    Represents a pending or resolved invitation sent to a user (by email)
    to join a shared trip collaboration. The token is used for the
    public accept-by-link flow.
    """

    invitee_email: str
    role: MemberRole
    status: InvitationStatus
    token: str
    expires_at: datetime
