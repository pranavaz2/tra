"""Domain and application errors for the Sharing bounded context."""

from __future__ import annotations

from uuid import UUID

from app.shared.domain.errors import ConflictError, DomainError, NotFoundError


class CollaborationNotFoundError(NotFoundError):
    """The requested TripCollaboration does not exist."""

    code = "collaboration_not_found"

    def __init__(self, id_or_trip: UUID | str) -> None:
        super().__init__("collaboration", id_or_trip)


class CollaborationAlreadyExistsError(ConflictError):
    """The trip already has a collaboration record."""

    code = "collaboration_already_exists"

    def __init__(self, trip_id: str) -> None:
        super().__init__(f"Trip '{trip_id}' already has a collaboration.")


class CollaborationAlreadyLockedError(DomainError):
    """Mutations are disallowed on a deleted collaboration."""

    code = "collaboration_already_locked"

    def __init__(self) -> None:
        super().__init__("This collaboration is deleted and cannot be modified.")


class MemberNotFoundError(NotFoundError):
    """The requested TripMember does not exist within this collaboration."""

    code = "member_not_found"

    def __init__(self, member_id: UUID | str) -> None:
        super().__init__("member", member_id)


class InvitationNotFoundError(NotFoundError):
    """The requested Invitation does not exist within this collaboration."""

    code = "invitation_not_found"

    def __init__(self, invitation_id: UUID | str) -> None:
        super().__init__("invitation", invitation_id)


class InvitationAlreadyExistsError(ConflictError):
    """A PENDING invitation for this email address already exists."""

    code = "invitation_already_exists"

    def __init__(self, email: str) -> None:
        super().__init__(
            f"A pending invitation for '{email}' already exists."
        )


class CannotRemoveOwnerError(DomainError):
    """The OWNER of a collaboration cannot be removed."""

    code = "cannot_remove_owner"

    def __init__(self) -> None:
        super().__init__("The trip owner cannot be removed from the collaboration.")


class CannotChangeOwnerRoleError(DomainError):
    """The OWNER's role cannot be changed, and no member can be promoted to OWNER."""

    code = "cannot_change_owner_role"

    def __init__(self, detail: str = "") -> None:
        msg = "Owner role cannot be changed."
        if detail:
            msg = detail
        super().__init__(msg)


class InvalidInvitationStatusError(DomainError):
    """The invitation is not in the expected status for this operation."""

    code = "invalid_invitation_status"

    def __init__(
        self,
        *,
        invitation_id: str,
        current_status: str,
        expected_status: str,
    ) -> None:
        super().__init__(
            f"Invitation '{invitation_id}' has status '{current_status}', "
            f"but '{expected_status}' was required."
        )
        self.invitation_id = invitation_id
        self.current_status = current_status
        self.expected_status = expected_status


class OnlyOwnerCanModifyError(DomainError):
    """Only the trip OWNER is permitted to perform this operation."""

    code = "only_owner_can_modify"

    def __init__(self, action: str = "perform this action") -> None:
        super().__init__(f"Only the trip owner is permitted to {action}.")


class PublicSharingNotEnabledError(DomainError):
    """The share token cannot be rotated when public sharing is disabled."""

    code = "public_sharing_not_enabled"

    def __init__(self) -> None:
        super().__init__(
            "Public sharing is not enabled. Enable public sharing before rotating the token."
        )
