"""TripMember entity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.shared.domain.entity import Entity


@dataclass(kw_only=True, eq=False)
class TripMember(Entity[MemberId]):
    """
    TripMember entity.

    Represents a user who has been granted access to a shared trip.
    A member is created when an invitation is accepted, or when the
    OWNER record is bootstrapped during collaboration creation.
    """

    user_id: UserId
    role: MemberRole
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))
