"""Unit tests for SharingService using in-memory test doubles."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest

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
    CollaborationSummary,
    InvitationSummary,
    MemberSummary,
    ShareTokenSummary,
)
from app.modules.travel.sharing.application.queries import (
    GetCollaborationQuery,
    ListInvitationsQuery,
    ListMembersQuery,
)
from app.modules.travel.sharing.application.sharing_service import SharingService
from app.modules.travel.sharing.domain.entities.invitation import Invitation
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
from app.modules.travel.sharing.domain.enums.invitation_status import InvitationStatus
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.errors import (
    CollaborationAlreadyExistsError,
    CollaborationNotFoundError,
    OnlyOwnerCanModifyError,
)
from app.modules.travel.sharing.domain.value_objects.collaboration_id import (
    CollaborationId,
)
from app.modules.travel.sharing.domain.value_objects.invitation_id import InvitationId
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.infrastructure.clock import FixedClock

# ──────────────────────────────────────────────────────────────────────────── #
# Constants                                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

FIXED_TIME = datetime(2026, 7, 16, 12, 0, 0, tzinfo=UTC)
FIXED_OWNER_UUID = UUID("da2c388a-2114-41d6-848e-6701bbabefd4")
FIXED_TRIP_UUID = UUID("b1836585-780c-40ef-8e8a-02d9a7442342")
FIXED_COLLAB_UUID = UUID("e819bcf8-87b4-4b55-8736-f3316dbcd3bf")
FIXED_MEMBER_UUID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


# ──────────────────────────────────────────────────────────────────────────── #
# Test Doubles                                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class InMemoryCollaborationRepository:
    """In-memory ITripCollaborationRepository."""

    def __init__(self) -> None:
        self._store: dict[UUID, TripCollaboration] = {}

    async def find_by_id(
        self, collaboration_id: CollaborationId
    ) -> TripCollaboration | None:
        return self._store.get(collaboration_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> TripCollaboration | None:
        return next(
            (
                c
                for c in self._store.values()
                if c.trip_id == trip_id and not c.is_deleted
            ),
            None,
        )

    async def find_by_share_token(self, token: str) -> TripCollaboration | None:
        return next(
            (
                c
                for c in self._store.values()
                if c.share_token and str(c.share_token) == token and c.is_public
            ),
            None,
        )

    async def save(self, collaboration: TripCollaboration) -> None:
        self._store[collaboration.collaboration_id.value] = collaboration

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        return any(
            c.trip_id == trip_id and not c.is_deleted for c in self._store.values()
        )


class InMemoryInvitationRepository:
    """In-memory IInvitationRepository."""

    def __init__(self, collab_repo: InMemoryCollaborationRepository) -> None:
        self._collab_repo = collab_repo

    async def find_by_token(self, token: str) -> Invitation | None:
        for collab in self._collab_repo._store.values():
            for inv in collab.invitations:
                if inv.token == token and inv.status == InvitationStatus.PENDING:
                    return inv
        return None


class InMemoryTripRepository:
    """In-memory ITripRepository."""

    def __init__(self) -> None:
        self._store: dict[UUID, Trip] = {}

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self._store.get(trip_id.value)

    async def save(self, trip: Trip) -> None:
        self._store[trip.trip_id.value] = trip

    async def exists(self, trip_id: TripId) -> bool:
        t = self._store.get(trip_id.value)
        return t is not None and not t.is_deleted

    async def delete(self, trip_id: TripId) -> None:
        self._store.pop(trip_id.value, None)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: Any = None,
        status_filter: Any = None,
    ) -> list[Trip]:
        return list(self._store.values())[:limit]

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        return list(self._store.values())

    async def exists_with_title(self, owner_id: UserId, title: TripTitle) -> bool:
        return False


class InMemoryEventPublisher:
    """In-memory EventPublisher for tracking published events."""

    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


class InMemoryUnitOfWork:
    """In-memory UnitOfWork that does nothing."""

    async def __aenter__(self) -> InMemoryUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class CyclicUUIDProvider:
    """Deterministic UUID provider that cycles through a list."""

    def __init__(self, values: list[UUID]) -> None:
        self._values = values
        self._index = 0

    def generate(self) -> UUID:
        value = self._values[self._index % len(self._values)]
        self._index += 1
        return value


# ──────────────────────────────────────────────────────────────────────────── #
# Composers                                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_service(
    uuids: list[UUID] | None = None,
) -> tuple[SharingService, InMemoryCollaborationRepository, InMemoryTripRepository, InMemoryEventPublisher]:
    if uuids is None:
        uuids = [FIXED_COLLAB_UUID, FIXED_MEMBER_UUID] + [UUID(int=i) for i in range(10)]
    collab_repo = InMemoryCollaborationRepository()
    inv_repo = InMemoryInvitationRepository(collab_repo)
    trip_repo = InMemoryTripRepository()
    uow = InMemoryUnitOfWork()
    pub = InMemoryEventPublisher()
    uuid_prov = CyclicUUIDProvider(uuids)
    clock = FixedClock(FIXED_TIME)

    service = SharingService(
        repository=collab_repo,
        invitation_repository=inv_repo,
        trip_repository=trip_repo,
        unit_of_work=uow,
        event_publisher=pub,
        uuid_provider=uuid_prov,
        clock=clock,
    )
    return service, collab_repo, trip_repo, pub


def _make_trip(
    owner_id: UserId,
    trip_id: TripId | None = None,
) -> Trip:
    """Build a minimal Trip aggregate for testing."""
    from datetime import date

    tid = trip_id or TripId(value=FIXED_TRIP_UUID)
    return Trip.create(
        trip_id=tid,
        owner_id=owner_id,
        title=TripTitle("Test Trip"),
        date_range=TripDateRange(
            departure_date=date(2026, 8, 1),
            return_date=date(2026, 8, 10),
        ),
        privacy=TripPrivacy.PRIVATE,
    )


# ──────────────────────────────────────────────────────────────────────────── #
# create_collaboration                                                            #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_create_collaboration_success() -> None:
    """Successfully bootstraps a collaboration for a trip owned by requester."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, pub = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    cmd = CreateCollaborationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.create_collaboration(cmd)

    assert isinstance(result, Success)
    summary: CollaborationSummary = result.value
    assert summary.owner_id == str(FIXED_OWNER_UUID)
    assert summary.trip_id == str(FIXED_TRIP_UUID)
    assert summary.member_count == 1
    assert summary.is_public is False


@pytest.mark.asyncio
async def test_create_collaboration_trip_not_found() -> None:
    """Returns Failure when the trip does not exist."""
    service, _, _, _ = _make_service()
    cmd = CreateCollaborationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.create_collaboration(cmd)
    assert isinstance(result, Failure)


@pytest.mark.asyncio
async def test_create_collaboration_not_owner_forbidden() -> None:
    """Returns Failure when requester is not the trip owner."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    non_owner = UserId.generate()
    service, _, trip_repo, _ = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    cmd = CreateCollaborationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(non_owner),
    )
    result = await service.create_collaboration(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_create_collaboration_duplicate_rejected() -> None:
    """Returns CollaborationAlreadyExistsError on second create."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, _, trip_repo, _ = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    cmd = CreateCollaborationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )
    await service.create_collaboration(cmd)
    result = await service.create_collaboration(cmd)

    assert isinstance(result, Failure)
    assert isinstance(result.error, CollaborationAlreadyExistsError)


# ──────────────────────────────────────────────────────────────────────────── #
# invite_member                                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


async def _bootstrap_collab(
    service: SharingService,
    collab_repo: InMemoryCollaborationRepository,
    trip_repo: InMemoryTripRepository,
    owner_id: UserId,
) -> None:
    """Helper: create and persist a collaboration."""
    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)
    cmd = CreateCollaborationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(owner_id),
    )
    await service.create_collaboration(cmd)


@pytest.mark.asyncio
async def test_invite_member_success() -> None:
    """OWNER can invite a member by email."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, pub = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    cmd = InviteMemberCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitee_email="alice@example.com",
        role="editor",
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.invite_member(cmd)

    assert isinstance(result, Success)
    summary: InvitationSummary = result.value
    assert summary.invitee_email == "alice@example.com"
    assert summary.role == MemberRole.EDITOR.value
    assert summary.status == InvitationStatus.PENDING.value


@pytest.mark.asyncio
async def test_invite_member_non_owner_rejected() -> None:
    """Non-OWNER cannot invite members."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    cmd = InviteMemberCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitee_email="alice@example.com",
        role="editor",
        requester_id=str(UserId.generate()),
    )
    result = await service.invite_member(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, OnlyOwnerCanModifyError)


@pytest.mark.asyncio
async def test_invite_member_collaboration_not_found() -> None:
    """Returns CollaborationNotFoundError when collaboration doesn't exist."""
    service, _, _, _ = _make_service()
    cmd = InviteMemberCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitee_email="alice@example.com",
        role="editor",
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.invite_member(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, CollaborationNotFoundError)


# ──────────────────────────────────────────────────────────────────────────── #
# accept/decline/revoke invitation                                                #
# ──────────────────────────────────────────────────────────────────────────── #


async def _invite_member(
    service: SharingService,
    *,
    owner_id: UserId,
    email: str = "alice@example.com",
    role: str = "editor",
) -> str:
    """Helper: invite and return invitation_id."""
    cmd = InviteMemberCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitee_email=email,
        role=role,
        requester_id=str(owner_id),
    )
    result = await service.invite_member(cmd)
    assert isinstance(result, Success)
    return result.value.invitation_id


@pytest.mark.asyncio
async def test_accept_invitation_adds_member() -> None:
    """Accepting invitation adds a new member to the collaboration."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, pub = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    inv_id = await _invite_member(service, owner_id=owner_id)

    new_user = UserId.generate()
    accept_cmd = AcceptInvitationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitation_id=inv_id,
        requester_id=str(new_user),
    )
    result = await service.accept_invitation(accept_cmd)

    assert isinstance(result, Success)
    member: MemberSummary = result.value
    assert member.role == MemberRole.EDITOR.value

    # Collaboration now has 2 members (OWNER + new member)
    collab = await collab_repo.find_by_trip_id(TripId(value=FIXED_TRIP_UUID))
    assert collab is not None
    assert len(collab.members) == 2


@pytest.mark.asyncio
async def test_decline_invitation_success() -> None:
    """Declining an invitation sets its status to DECLINED."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    inv_id = await _invite_member(service, owner_id=owner_id)

    cmd = DeclineInvitationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitation_id=inv_id,
        requester_id=str(UserId.generate()),
    )
    result = await service.decline_invitation(cmd)
    assert isinstance(result, Success)

    collab = await collab_repo.find_by_trip_id(TripId(value=FIXED_TRIP_UUID))
    assert collab is not None
    inv = collab._find_invitation(InvitationId.from_str(inv_id))
    assert inv is not None
    assert inv.status == InvitationStatus.DECLINED


@pytest.mark.asyncio
async def test_revoke_invitation_success() -> None:
    """OWNER can revoke a pending invitation."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    inv_id = await _invite_member(service, owner_id=owner_id)

    cmd = RevokeInvitationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitation_id=inv_id,
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.revoke_invitation(cmd)
    assert isinstance(result, Success)


# ──────────────────────────────────────────────────────────────────────────── #
# change_member_role / remove_member                                              #
# ──────────────────────────────────────────────────────────────────────────── #


async def _add_member(
    service: SharingService,
    collab_repo: InMemoryCollaborationRepository,
    *,
    owner_id: UserId,
    email: str = "member@example.com",
) -> str:
    """Helper: invite + accept, return member_id."""
    inv_id = await _invite_member(service, owner_id=owner_id, email=email)
    accept_cmd = AcceptInvitationCommand(
        trip_id=str(FIXED_TRIP_UUID),
        invitation_id=inv_id,
        requester_id=str(UserId.generate()),
    )
    result = await service.accept_invitation(accept_cmd)
    assert isinstance(result, Success)
    return result.value.member_id


@pytest.mark.asyncio
async def test_change_member_role_success() -> None:
    """OWNER can change a member's role to VIEWER."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    member_id = await _add_member(service, collab_repo, owner_id=owner_id)

    cmd = ChangeMemberRoleCommand(
        trip_id=str(FIXED_TRIP_UUID),
        member_id=member_id,
        new_role="viewer",
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.change_member_role(cmd)
    assert isinstance(result, Success)
    assert result.value.role == MemberRole.VIEWER.value


@pytest.mark.asyncio
async def test_remove_member_success() -> None:
    """OWNER can remove a non-OWNER member."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    member_id = await _add_member(service, collab_repo, owner_id=owner_id)

    cmd = RemoveMemberCommand(
        trip_id=str(FIXED_TRIP_UUID),
        member_id=member_id,
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.remove_member(cmd)
    assert isinstance(result, Success)

    collab = await collab_repo.find_by_trip_id(TripId(value=FIXED_TRIP_UUID))
    assert collab is not None
    assert len(collab.members) == 1  # only owner left


# ──────────────────────────────────────────────────────────────────────────── #
# Public sharing                                                                  #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_enable_public_sharing_success() -> None:
    """enable_public_sharing returns a share token."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    cmd = EnablePublicSharingCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.enable_public_sharing(cmd)

    assert isinstance(result, Success)
    token_summary: ShareTokenSummary = result.value
    assert token_summary.is_public is True
    assert len(token_summary.share_token) == 64


@pytest.mark.asyncio
async def test_disable_public_sharing_success() -> None:
    """disable_public_sharing returns Success."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, _, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, None, trip_repo, owner_id)  # type: ignore[arg-type]

    # enable first
    enable_cmd = EnablePublicSharingCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )
    await service.enable_public_sharing(enable_cmd)

    disable_cmd = DisablePublicSharingCommand(
        trip_id=str(FIXED_TRIP_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )
    result = await service.disable_public_sharing(disable_cmd)
    assert isinstance(result, Success)


@pytest.mark.asyncio
async def test_rotate_share_token_changes_token() -> None:
    """rotate_share_token generates a different token."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    enable_result = await service.enable_public_sharing(
        EnablePublicSharingCommand(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(FIXED_OWNER_UUID),
        )
    )
    assert isinstance(enable_result, Success)
    first_token = enable_result.value.share_token

    rotate_result = await service.rotate_share_token(
        RotateShareTokenCommand(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(FIXED_OWNER_UUID),
        )
    )
    assert isinstance(rotate_result, Success)
    assert rotate_result.value.share_token != first_token


# ──────────────────────────────────────────────────────────────────────────── #
# Queries                                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_get_collaboration_success() -> None:
    """get_collaboration returns summary for a member of the collaboration."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    result = await service.get_collaboration(
        GetCollaborationQuery(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(FIXED_OWNER_UUID),
        )
    )
    assert isinstance(result, Success)
    summary: CollaborationSummary = result.value
    assert summary.owner_id == str(FIXED_OWNER_UUID)


@pytest.mark.asyncio
async def test_get_collaboration_non_member_forbidden() -> None:
    """Non-member cannot view collaboration details."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    result = await service.get_collaboration(
        GetCollaborationQuery(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(UserId.generate()),
        )
    )
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_list_members_returns_page() -> None:
    """list_members returns a paginated list of members."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    result = await service.list_members(
        ListMembersQuery(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(FIXED_OWNER_UUID),
            limit=10,
        )
    )
    assert isinstance(result, Success)
    assert len(result.value.items) == 1  # only the OWNER member
    assert result.value.items[0].role == MemberRole.OWNER.value


@pytest.mark.asyncio
async def test_list_invitations_only_for_owner() -> None:
    """list_invitations returns Failure for non-OWNER."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, collab_repo, trip_repo, _ = _make_service()
    await _bootstrap_collab(service, collab_repo, trip_repo, owner_id)

    result = await service.list_invitations(
        ListInvitationsQuery(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(UserId.generate()),
            limit=10,
        )
    )
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)
