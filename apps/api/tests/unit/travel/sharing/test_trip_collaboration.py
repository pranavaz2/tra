"""Unit tests for TripCollaboration aggregate root and domain entities."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.sharing.domain.entities.invitation import Invitation
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
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
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


# ──────────────────────────────────────────────────────────────────────────── #
# Test helpers                                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_collab(
    owner_id: UserId | None = None,
) -> TripCollaboration:
    """Create a minimal TripCollaboration for testing."""
    oid = owner_id or UserId.generate()
    return TripCollaboration.create(
        collaboration_id=CollaborationId.generate(),
        trip_id=TripId.generate(),
        owner_id=oid,
        owner_member_id=MemberId.generate(),
    )


# ──────────────────────────────────────────────────────────────────────────── #
# Creation                                                                        #
# ──────────────────────────────────────────────────────────────────────────── #


def test_collaboration_creation_bootstraps_owner_member() -> None:
    """TripCollaboration.create adds the OWNER as the first member."""
    owner_id = UserId.generate()
    owner_mid = MemberId.generate()
    collab = TripCollaboration.create(
        collaboration_id=CollaborationId.generate(),
        trip_id=TripId.generate(),
        owner_id=owner_id,
        owner_member_id=owner_mid,
    )

    assert len(collab.members) == 1
    assert collab.members[0].user_id == owner_id
    assert collab.members[0].role == MemberRole.OWNER
    assert collab.members[0].entity_id == owner_mid
    assert collab.is_public is False
    assert collab.share_token is None


def test_collaboration_creation_has_no_pending_events() -> None:
    """create() should not push any domain events automatically."""
    collab = _make_collab()
    events = collab.pop_events()
    assert events == []


# ──────────────────────────────────────────────────────────────────────────── #
# Invitations                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


def test_invite_member_success() -> None:
    """OWNER can invite a new member with EDITOR or VIEWER role."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    collab.pop_events()

    invitation = collab.invite_member(
        invitation_id=InvitationId.generate(),
        invitee_email="alice@example.com",
        role=MemberRole.EDITOR,
        requester_id=owner_id,
    )

    assert len(collab.invitations) == 1
    assert invitation.invitee_email == "alice@example.com"
    assert invitation.role == MemberRole.EDITOR
    assert invitation.status == InvitationStatus.PENDING

    events = collab.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], TripInviteSent)
    assert events[0].invitee_email == "alice@example.com"


def test_invite_member_normalizes_email() -> None:
    """Email is normalized to lowercase stripped form."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    invitation = collab.invite_member(
        invitation_id=InvitationId.generate(),
        invitee_email="  ALICE@EXAMPLE.COM  ",
        role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    assert invitation.invitee_email == "alice@example.com"


def test_invite_member_forbidden_for_non_owner() -> None:
    """Non-OWNER cannot invite members."""
    collab = _make_collab()
    non_owner = UserId.generate()
    with pytest.raises(OnlyOwnerCanModifyError):
        collab.invite_member(
            invitation_id=InvitationId.generate(),
            invitee_email="bob@example.com",
            role=MemberRole.EDITOR,
            requester_id=non_owner,
        )


def test_invite_member_with_owner_role_rejected() -> None:
    """Role cannot be OWNER when inviting."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    with pytest.raises(CannotChangeOwnerRoleError):
        collab.invite_member(
            invitation_id=InvitationId.generate(),
            invitee_email="charlie@example.com",
            role=MemberRole.OWNER,
            requester_id=owner_id,
        )


def test_invite_member_duplicate_pending_rejected() -> None:
    """Cannot send a second PENDING invitation to the same email."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    collab.invite_member(
        invitation_id=InvitationId.generate(),
        invitee_email="dave@example.com",
        role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    with pytest.raises(InvitationAlreadyExistsError):
        collab.invite_member(
            invitation_id=InvitationId.generate(),
            invitee_email="DAVE@EXAMPLE.COM",
            role=MemberRole.EDITOR,
            requester_id=owner_id,
        )


def test_accept_invitation_adds_member_and_fires_event() -> None:
    """Accepting a PENDING invitation promotes the user to a member."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email="eve@example.com",
        role=MemberRole.EDITOR,
        requester_id=owner_id,
    )
    collab.pop_events()

    new_user = UserId.generate()
    new_mid = MemberId.generate()
    new_member = collab.accept_invitation(
        invitation_id=inv_id,
        accepting_user_id=new_user,
        new_member_id=new_mid,
    )

    assert len(collab.members) == 2
    assert new_member.user_id == new_user
    assert new_member.role == MemberRole.EDITOR

    invitation = collab._find_invitation(inv_id)
    assert invitation is not None
    assert invitation.status == InvitationStatus.ACCEPTED

    events = collab.pop_events()
    assert any(isinstance(e, TripInviteAccepted) for e in events)


def test_accept_already_accepted_invitation_raises() -> None:
    """Cannot accept an already-accepted invitation."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email="frank@example.com",
        role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    collab.accept_invitation(
        invitation_id=inv_id,
        accepting_user_id=UserId.generate(),
        new_member_id=MemberId.generate(),
    )
    with pytest.raises(InvalidInvitationStatusError):
        collab.accept_invitation(
            invitation_id=inv_id,
            accepting_user_id=UserId.generate(),
            new_member_id=MemberId.generate(),
        )


def test_accept_expired_invitation_raises() -> None:
    """An expired invitation cannot be accepted."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email="grace@example.com",
        role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    # Force expires_at to the past
    inv = collab._find_invitation(inv_id)
    assert inv is not None
    inv.expires_at = datetime.now(UTC) - timedelta(days=1)

    with pytest.raises(InvalidInvitationStatusError):
        collab.accept_invitation(
            invitation_id=inv_id,
            accepting_user_id=UserId.generate(),
            new_member_id=MemberId.generate(),
        )


def test_decline_invitation_fires_event() -> None:
    """Declining a PENDING invitation sets status to DECLINED."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email="heidi@example.com",
        role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    collab.pop_events()

    collab.decline_invitation(invitation_id=inv_id)

    inv = collab._find_invitation(inv_id)
    assert inv is not None
    assert inv.status == InvitationStatus.DECLINED

    events = collab.pop_events()
    assert any(isinstance(e, TripInviteDeclined) for e in events)


def test_revoke_invitation_by_owner() -> None:
    """OWNER can revoke a PENDING invitation."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email="ivan@example.com",
        role=MemberRole.EDITOR,
        requester_id=owner_id,
    )

    collab.revoke_invitation(invitation_id=inv_id, requester_id=owner_id)
    inv = collab._find_invitation(inv_id)
    assert inv is not None
    assert inv.status == InvitationStatus.REVOKED


def test_revoke_invitation_by_non_owner_raises() -> None:
    """Non-OWNER cannot revoke invitations."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email="judy@example.com",
        role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    with pytest.raises(OnlyOwnerCanModifyError):
        collab.revoke_invitation(invitation_id=inv_id, requester_id=UserId.generate())


def test_invitation_not_found_raises() -> None:
    """Operations on a non-existent invitation_id raise InvitationNotFoundError."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    missing = InvitationId.generate()
    with pytest.raises(InvitationNotFoundError):
        collab.decline_invitation(invitation_id=missing)
    with pytest.raises(InvitationNotFoundError):
        collab.revoke_invitation(invitation_id=missing, requester_id=owner_id)
    with pytest.raises(InvitationNotFoundError):
        collab.accept_invitation(
            invitation_id=missing,
            accepting_user_id=UserId.generate(),
            new_member_id=MemberId.generate(),
        )


# ──────────────────────────────────────────────────────────────────────────── #
# Member management                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


def _add_member(
    collab: TripCollaboration,
    owner_id: UserId,
    *,
    role: MemberRole = MemberRole.EDITOR,
) -> TripMember:
    """Helper: invite + accept in one step."""
    inv_id = InvitationId.generate()
    collab.invite_member(
        invitation_id=inv_id,
        invitee_email=f"{inv_id}@example.com",
        role=role,
        requester_id=owner_id,
    )
    new_user = UserId.generate()
    new_mid = MemberId.generate()
    member = collab.accept_invitation(
        invitation_id=inv_id,
        accepting_user_id=new_user,
        new_member_id=new_mid,
    )
    collab.pop_events()
    return member


def test_change_member_role_success() -> None:
    """OWNER can change a non-OWNER member's role."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    member = _add_member(collab, owner_id, role=MemberRole.EDITOR)

    collab.change_member_role(
        member_id=member.entity_id,
        new_role=MemberRole.VIEWER,
        requester_id=owner_id,
    )
    updated = collab._find_member(member.entity_id)
    assert updated is not None
    assert updated.role == MemberRole.VIEWER

    events = collab.pop_events()
    role_events = [e for e in events if isinstance(e, TripMemberRoleChanged)]
    assert len(role_events) == 1
    assert role_events[0].old_role == MemberRole.EDITOR.value
    assert role_events[0].new_role == MemberRole.VIEWER.value


def test_change_member_role_to_owner_rejected() -> None:
    """Cannot promote a member to OWNER."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    member = _add_member(collab, owner_id)
    with pytest.raises(CannotChangeOwnerRoleError):
        collab.change_member_role(
            member_id=member.entity_id,
            new_role=MemberRole.OWNER,
            requester_id=owner_id,
        )


def test_change_owner_role_rejected() -> None:
    """OWNER's own role cannot be changed."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    owner_member = collab._find_owner_member()
    assert owner_member is not None
    with pytest.raises(CannotChangeOwnerRoleError):
        collab.change_member_role(
            member_id=owner_member.entity_id,
            new_role=MemberRole.EDITOR,
            requester_id=owner_id,
        )


def test_change_role_forbidden_for_non_owner() -> None:
    """Non-OWNER cannot change roles."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    member = _add_member(collab, owner_id)
    with pytest.raises(OnlyOwnerCanModifyError):
        collab.change_member_role(
            member_id=member.entity_id,
            new_role=MemberRole.VIEWER,
            requester_id=UserId.generate(),
        )


def test_remove_member_success_fires_event() -> None:
    """OWNER can remove a non-OWNER member."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    member = _add_member(collab, owner_id)
    initial_count = len(collab.members)

    collab.remove_member(member_id=member.entity_id, requester_id=owner_id)

    assert len(collab.members) == initial_count - 1
    assert collab._find_member(member.entity_id) is None

    events = collab.pop_events()
    assert any(isinstance(e, TripMemberRemoved) for e in events)


def test_remove_owner_raises() -> None:
    """OWNER cannot be removed from the collaboration."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    owner_member = collab._find_owner_member()
    assert owner_member is not None
    with pytest.raises(CannotRemoveOwnerError):
        collab.remove_member(
            member_id=owner_member.entity_id,
            requester_id=owner_id,
        )


def test_remove_non_existent_member_raises() -> None:
    """Removing a member that does not exist raises MemberNotFoundError."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    with pytest.raises(MemberNotFoundError):
        collab.remove_member(
            member_id=MemberId.generate(),
            requester_id=owner_id,
        )


# ──────────────────────────────────────────────────────────────────────────── #
# Public sharing                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


def test_enable_public_sharing_generates_token_and_fires_event() -> None:
    """enable_public_sharing sets is_public and returns a ShareToken."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)

    token = collab.enable_public_sharing(requester_id=owner_id)

    assert collab.is_public is True
    assert collab.share_token is not None
    assert str(collab.share_token) == str(token)
    assert len(str(token)) == 64  # 32 bytes → 64 hex chars

    events = collab.pop_events()
    assert any(isinstance(e, TripSharedPublicly) for e in events)


def test_enable_public_sharing_forbidden_for_non_owner() -> None:
    """Non-OWNER cannot enable public sharing."""
    collab = _make_collab()
    with pytest.raises(OnlyOwnerCanModifyError):
        collab.enable_public_sharing(requester_id=UserId.generate())


def test_disable_public_sharing_clears_token_and_fires_event() -> None:
    """disable_public_sharing clears the token and fires TripShareRevoked."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    collab.enable_public_sharing(requester_id=owner_id)
    collab.pop_events()

    collab.disable_public_sharing(requester_id=owner_id)

    assert collab.is_public is False
    assert collab.share_token is None

    events = collab.pop_events()
    assert any(isinstance(e, TripShareRevoked) for e in events)


def test_disable_public_sharing_forbidden_for_non_owner() -> None:
    """Non-OWNER cannot disable public sharing."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    collab.enable_public_sharing(requester_id=owner_id)
    with pytest.raises(OnlyOwnerCanModifyError):
        collab.disable_public_sharing(requester_id=UserId.generate())


def test_rotate_share_token_changes_token() -> None:
    """rotate_share_token generates a new token and fires TripSharedPublicly."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    original_token = collab.enable_public_sharing(requester_id=owner_id)
    collab.pop_events()

    new_token = collab.rotate_share_token(requester_id=owner_id)

    assert str(new_token) != str(original_token)
    assert str(collab.share_token) == str(new_token)

    events = collab.pop_events()
    assert any(isinstance(e, TripSharedPublicly) for e in events)


def test_rotate_share_token_without_public_sharing_raises() -> None:
    """Cannot rotate token when public sharing is disabled."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    with pytest.raises(PublicSharingNotEnabledError):
        collab.rotate_share_token(requester_id=owner_id)


def test_rotate_share_token_forbidden_for_non_owner() -> None:
    """Non-OWNER cannot rotate the share token."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    collab.enable_public_sharing(requester_id=owner_id)
    with pytest.raises(OnlyOwnerCanModifyError):
        collab.rotate_share_token(requester_id=UserId.generate())


# ──────────────────────────────────────────────────────────────────────────── #
# Soft-delete / locked state                                                      #
# ──────────────────────────────────────────────────────────────────────────── #


def test_deleted_collaboration_raises_on_invite() -> None:
    """All mutations fail on a deleted collaboration."""
    owner_id = UserId.generate()
    collab = _make_collab(owner_id=owner_id)
    collab.delete()

    with pytest.raises(CollaborationAlreadyLockedError):
        collab.invite_member(
            invitation_id=InvitationId.generate(),
            invitee_email="kate@example.com",
            role=MemberRole.VIEWER,
            requester_id=owner_id,
        )


def test_double_delete_raises() -> None:
    """Deleting an already-deleted collaboration raises."""
    collab = _make_collab()
    collab.delete()
    with pytest.raises(CollaborationAlreadyLockedError):
        collab.delete()


# ──────────────────────────────────────────────────────────────────────────── #
# Value objects                                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


def test_collaboration_id_round_trip() -> None:
    """CollaborationId.from_str / __str__ round-trip."""
    c = CollaborationId.generate()
    assert CollaborationId.from_str(str(c)) == c


def test_member_id_round_trip() -> None:
    """MemberId.from_str / __str__ round-trip."""
    m = MemberId.generate()
    assert MemberId.from_str(str(m)) == m


def test_invitation_id_round_trip() -> None:
    """InvitationId.from_str / __str__ round-trip."""
    i = InvitationId.generate()
    assert InvitationId.from_str(str(i)) == i


def test_share_token_is_64_hex_chars() -> None:
    """ShareToken.generate() produces a 64-character hex string."""
    from app.modules.travel.sharing.domain.value_objects.share_token import ShareToken

    t = ShareToken.generate()
    assert len(str(t)) == 64
    assert all(c in "0123456789abcdef" for c in str(t))


def test_share_token_is_unique_each_time() -> None:
    """Two generate() calls produce different tokens."""
    from app.modules.travel.sharing.domain.value_objects.share_token import ShareToken

    t1 = ShareToken.generate()
    t2 = ShareToken.generate()
    assert str(t1) != str(t2)
