"""InvitationStatus enum."""

from __future__ import annotations

from enum import Enum


class InvitationStatus(str, Enum):
    """Lifecycle status of a trip collaboration invitation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    REVOKED = "revoked"
