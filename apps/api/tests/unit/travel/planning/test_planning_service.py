"""Unit tests for PlanningService using in-memory test doubles."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.identity.authentication.infrastructure.unit_of_work import (
    InMemoryUnitOfWork,
)
from app.modules.travel.planning.application.commands import (
    AcceptProposalCommand,
    RejectProposalCommand,
    RequestProposalCommand,
)
from app.modules.travel.planning.application.planning_service import (
    PlanningService,
)
from app.modules.travel.planning.application.queries import (
    GetProposalQuery,
)
from app.modules.travel.planning.domain.entities.trip_proposal import TripProposal
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.planning.domain.value_objects.proposal_status import (
    ProposalStatus,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.services.ai.mock import MockPlanningEngine
from app.modules.travel.planning.domain.errors import InvalidProposalStatusTransitionError
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.uuid_provider import FixedUUIDProvider, StandardUUIDProvider
from app.shared.infrastructure.clock import FixedClock

# ─────────────────────────────────────────────────────────────────────────────
# Test doubles
# ─────────────────────────────────────────────────────────────────────────────


class InMemoryTripProposalRepository:
    """In-memory ITripProposalRepository for unit tests."""

    def __init__(self) -> None:
        self._store: dict[UUID, TripProposal] = {}

    async def find_by_id(self, proposal_id: ProposalId) -> TripProposal | None:
        return self._store.get(proposal_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> TripProposal | None:
        props = [p for p in self._store.values() if p.trip_id == trip_id and not p.is_deleted]
        if not props:
            return None
        props.sort(key=lambda p: (p.created_at, str(p.proposal_id)), reverse=True)
        return props[0]

    async def find_active_by_trip_id(self, trip_id: TripId) -> TripProposal | None:
        props = [
            p
            for p in self._store.values()
            if p.trip_id == trip_id
            and not p.is_deleted
            and p.status in (ProposalStatus.QUEUED, ProposalStatus.GENERATING)
        ]
        if not props:
            return None
        props.sort(key=lambda p: (p.created_at, str(p.proposal_id)), reverse=True)
        return props[0]

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: ProposalId | None = None,
    ) -> list[TripProposal]:
        props = [
            p for p in self._store.values() if p.owner_id == owner_id and not p.is_deleted
        ]
        props.sort(key=lambda p: (p.created_at, str(p.proposal_id)), reverse=True)
        if after_id is not None:
            cursor = self._store.get(after_id.value)
            if cursor:
                props = [
                    p
                    for p in props
                    if p.created_at < cursor.created_at
                    or (
                        p.created_at == cursor.created_at
                        and str(p.proposal_id) < str(cursor.proposal_id)
                    )
                ]
        return props[:limit]

    async def save(self, proposal: TripProposal) -> None:
        self._store[proposal.proposal_id.value] = proposal

    async def delete(self, proposal_id: ProposalId) -> None:
        self._store.pop(proposal_id.value, None)

    async def exists(self, proposal_id: ProposalId) -> bool:
        proposal = self._store.get(proposal_id.value)
        return proposal is not None and not proposal.is_deleted


class InMemoryTripRepository:
    """In-memory ITripRepository for unit tests."""

    def __init__(self) -> None:
        self._store: dict[UUID, Trip] = {}

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self._store.get(trip_id.value)

    async def save(self, trip: Trip) -> None:
        self._store[trip.trip_id.value] = trip

    async def exists(self, trip_id: TripId) -> bool:
        trip = self._store.get(trip_id.value)
        return trip is not None and not trip.is_deleted

    async def delete(self, trip_id: TripId) -> None:
        self._store.pop(trip_id.value, None)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: TripId | None = None,
        status_filter: Any = None,
    ) -> list[Trip]:
        return list(self._store.values())[:limit]

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        return list(self._store.values())

    async def exists_with_title(self, owner_id: UserId, title: TripTitle) -> bool:
        return False


class _InMemoryEventPublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


class InMemoryItineraryRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Itinerary] = {}

    async def find_by_id(self, itinerary_id: ItineraryId) -> Itinerary | None:
        return self._store.get(itinerary_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        for itin in self._store.values():
            if itin.trip_id == trip_id and not itin.is_deleted:
                return itin
        return None

    async def save(self, itinerary: Itinerary) -> None:
        self._store[itinerary.itinerary_id.value] = itinerary

    async def delete(self, itinerary_id: ItineraryId) -> None:
        self._store.pop(itinerary_id.value, None)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures & Setup Helpers
# ─────────────────────────────────────────────────────────────────────────────


OWNER_ID = str(uuid.uuid4())
OTHER_USER_ID = str(uuid.uuid4())
FIXED_PROPOSAL_UUID = uuid.UUID("00000000-0000-4000-8000-000000000002")
FIXED_TIME = datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC)


def _make_service(
    *,
    proposal_uuid: UUID = FIXED_PROPOSAL_UUID,
    itin_repo: InMemoryItineraryRepository | None = None,
    uuid_provider: Any = None,
    uow: InMemoryUnitOfWork | None = None,
) -> tuple[
    PlanningService,
    InMemoryTripProposalRepository,
    InMemoryTripRepository,
    _InMemoryEventPublisher,
]:
    repo = InMemoryTripProposalRepository()
    trip_repo = InMemoryTripRepository()
    pub = _InMemoryEventPublisher()
    actual_uow = uow or InMemoryUnitOfWork()
    service = PlanningService(
        repository=repo,
        trip_repository=trip_repo,
        planning_engine=MockPlanningEngine(),
        unit_of_work=actual_uow,
        event_publisher=pub,
        uuid_provider=uuid_provider or FixedUUIDProvider([proposal_uuid]),
        clock=FixedClock(FIXED_TIME),
        itinerary_repository=itin_repo,
    )
    return service, repo, trip_repo, pub


# ─────────────────────────────────────────────────────────────────────────────
# Test cases
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_proposal_success() -> None:
    service, _repo, trip_repo, _pub = _make_service()

    # Create and save a live trip
    trip_uuid = uuid.uuid4()
    trip = Trip.create(
        trip_id=TripId(value=trip_uuid),
        owner_id=UserId.from_str(OWNER_ID),
        title=TripTitle("Lisbon Exploration"),
    )
    await trip_repo.save(trip)

    cmd = RequestProposalCommand(
        trip_id=str(trip_uuid),
        requester_id=OWNER_ID,
        destination="Lisbon",
        duration_days=3,
        budget_level="mid_range",
        interests=["food", "history"],
        travel_style="balanced",
        special_requirements="",
    )

    result = await service.request_proposal(cmd)
    assert isinstance(result, Success)
    summary = result.value
    assert summary.status == ProposalStatus.READY
    assert summary.result is not None
    assert summary.result.summary == "A 3-day balanced trip to Lisbon with a mid_range budget."
    assert len(summary.result.days) == 3


@pytest.mark.asyncio
async def test_request_proposal_unauthorized_user() -> None:
    service, _repo, trip_repo, _ = _make_service()

    # Create and save a live trip
    trip_uuid = uuid.uuid4()
    trip = Trip.create(
        trip_id=TripId(value=trip_uuid),
        owner_id=UserId.from_str(OWNER_ID),
        title=TripTitle("Lisbon Exploration"),
    )
    await trip_repo.save(trip)

    cmd = RequestProposalCommand(
        trip_id=str(trip_uuid),
        requester_id=OTHER_USER_ID,  # Unauthorized requester
        destination="Lisbon",
        duration_days=3,
        budget_level="mid_range",
        interests=[],
        travel_style="balanced",
        special_requirements="",
    )

    result = await service.request_proposal(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


@pytest.mark.asyncio
async def test_request_proposal_trip_not_found() -> None:
    service, _, _, _ = _make_service()

    cmd = RequestProposalCommand(
        trip_id=str(uuid.uuid4()),  # Random non-existent trip ID
        requester_id=OWNER_ID,
        destination="Lisbon",
        duration_days=3,
        budget_level="mid_range",
        interests=[],
        travel_style="balanced",
        special_requirements="",
    )

    result = await service.request_proposal(cmd)
    assert isinstance(result, Failure)
    # Reuses TripNotFoundError from Trips module
    assert result.error.code == "trip_not_found"


@pytest.mark.asyncio
async def test_accept_proposal_success() -> None:
    service, repo, _trip_repo, _pub = _make_service()

    # Create proposal directly
    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Paris",
            duration_days=3,
            budget_level="budget",
            interests=(),
            travel_style="relaxed",
            special_requirements="",
        ),
    )
    # Move status to READY
    proposal.start_generation()
    proposal.complete_generation(
        result=await MockPlanningEngine().generate_plan(proposal.preferences),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    await repo.save(proposal)

    cmd = AcceptProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
    )

    result = await service.accept_proposal(cmd)
    assert isinstance(result, Success)
    assert result.value.status == ProposalStatus.ACCEPTED


@pytest.mark.asyncio
async def test_reject_proposal_success() -> None:
    service, repo, _trip_repo, _pub = _make_service()

    # Create proposal directly
    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Paris",
            duration_days=3,
            budget_level="budget",
            interests=(),
            travel_style="relaxed",
            special_requirements="",
        ),
    )
    # Move status to READY
    proposal.start_generation()
    proposal.complete_generation(
        result=await MockPlanningEngine().generate_plan(proposal.preferences),
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    await repo.save(proposal)

    cmd = RejectProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
    )

    result = await service.reject_proposal(cmd)
    assert isinstance(result, Success)
    assert result.value.status == ProposalStatus.REJECTED


@pytest.mark.asyncio
async def test_get_proposal_lazy_expiry() -> None:
    service, repo, _trip_repo, _pub = _make_service()

    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Paris",
            duration_days=3,
            budget_level="budget",
            interests=(),
            travel_style="relaxed",
            special_requirements="",
        ),
    )
    proposal.start_generation()
    # Expired 2 hours ago relative to FIXED_TIME
    expired_time = FIXED_TIME - timedelta(hours=2)
    proposal.complete_generation(
        result=await MockPlanningEngine().generate_plan(proposal.preferences),
        expires_at=expired_time,
    )
    await repo.save(proposal)

    query = GetProposalQuery(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
    )

    result = await service.get_proposal(query)
    assert isinstance(result, Success)
    # Return should reflect EXPIRED due to lazy validation
    assert result.value.status == ProposalStatus.EXPIRED

    # Check that status was updated in repository as well
    updated = await repo.find_by_id(proposal_id)
    assert updated.status == ProposalStatus.EXPIRED


@pytest.mark.asyncio
async def test_accept_proposal_applies_to_itinerary_atomically() -> None:
    itin_repo = InMemoryItineraryRepository()
    service, repo, _trip_repo, pub = _make_service(
        itin_repo=itin_repo,
        uuid_provider=StandardUUIDProvider(),
    )

    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Rome",
            duration_days=3,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        ),
    )
    proposal.start_generation()
    plan_result = await MockPlanningEngine().generate_plan(proposal.preferences)
    proposal.complete_generation(
        result=plan_result,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    await repo.save(proposal)

    # Accept proposal with apply_to_itinerary=True
    cmd = AcceptProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
        apply_to_itinerary=True,
    )

    result = await service.accept_proposal(cmd)
    assert isinstance(result, Success)
    assert result.value.status == ProposalStatus.ACCEPTED

    # Verify itinerary was created and populated with 3 days
    itinerary = await itin_repo.find_by_trip_id(trip_id)
    assert itinerary is not None
    assert len(itinerary.days) == 3
    # Check that day 1 has activities from mock planning engine
    assert len(itinerary.days[0].items) == 2
    assert "exploration" in itinerary.days[0].items[0].title.value.lower()


@pytest.mark.asyncio
async def test_accept_proposal_failure_during_application_rolls_back() -> None:
    class FailingItineraryRepository(InMemoryItineraryRepository):
        async def save(self, itinerary: Itinerary) -> None:
            raise RuntimeError("Database write error during itinerary persistence")

    failing_repo = FailingItineraryRepository()
    uow = InMemoryUnitOfWork()
    service, repo, _trip_repo, pub = _make_service(
        itin_repo=failing_repo,
        uuid_provider=StandardUUIDProvider(),
        uow=uow,
    )

    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Rome",
            duration_days=2,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        ),
    )
    proposal.start_generation()
    plan_result = await MockPlanningEngine().generate_plan(proposal.preferences)
    proposal.complete_generation(
        result=plan_result,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    await repo.save(proposal)

    cmd = AcceptProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
        apply_to_itinerary=True,
    )

    result = await service.accept_proposal(cmd)
    assert isinstance(result, Failure)
    assert uow.committed is False
    assert uow.rolled_back is True
    assert len(pub.published) == 0


@pytest.mark.asyncio
async def test_accept_proposal_unauthorized_and_invalid_state() -> None:
    itin_repo = InMemoryItineraryRepository()
    service, repo, _trip_repo, _pub = _make_service(
        itin_repo=itin_repo,
        uuid_provider=StandardUUIDProvider(),
    )

    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Rome",
            duration_days=2,
            budget_level="mid_range",
            interests=(),
            travel_style="balanced",
            special_requirements="",
        ),
    )
    # Not yet generated (status is QUEUED)
    await repo.save(proposal)

    # 1. Unauthorized user attempt
    unauth_cmd = AcceptProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OTHER_USER_ID,
        apply_to_itinerary=True,
    )
    result_unauth = await service.accept_proposal(unauth_cmd)
    assert isinstance(result_unauth, Failure)
    assert isinstance(result_unauth.error, ForbiddenError)

    # 2. Owner attempt while in invalid state (QUEUED, cannot transition to ACCEPTED)
    invalid_cmd = AcceptProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
        apply_to_itinerary=True,
    )
    result_invalid = await service.accept_proposal(invalid_cmd)
    assert isinstance(result_invalid, Failure)
    assert isinstance(result_invalid.error, InvalidProposalStatusTransitionError)

    # Ensure no itinerary was created
    assert await itin_repo.find_by_trip_id(trip_id) is None


@pytest.mark.asyncio
async def test_accept_proposal_without_itinerary_application_backward_compat() -> None:
    itin_repo = InMemoryItineraryRepository()
    service, repo, _trip_repo, pub = _make_service(
        itin_repo=itin_repo,
        uuid_provider=StandardUUIDProvider(),
    )

    proposal_id = ProposalId(value=FIXED_PROPOSAL_UUID)
    trip_id = TripId(value=uuid.uuid4())
    proposal = TripProposal.create(
        proposal_id=proposal_id,
        trip_id=trip_id,
        owner_id=UserId.from_str(OWNER_ID),
        preferences=PlanningPreferences(
            destination="Tokyo",
            duration_days=1,
            budget_level="budget",
            interests=(),
            travel_style="relaxed",
            special_requirements="",
        ),
    )
    proposal.start_generation()
    plan_result = await MockPlanningEngine().generate_plan(proposal.preferences)
    proposal.complete_generation(
        result=plan_result,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    await repo.save(proposal)

    # Explicitly set apply_to_itinerary=False (backward compatibility)
    cmd = AcceptProposalCommand(
        proposal_id=str(FIXED_PROPOSAL_UUID),
        requester_id=OWNER_ID,
        apply_to_itinerary=False,
    )

    result = await service.accept_proposal(cmd)
    assert isinstance(result, Success)
    assert result.value.status == ProposalStatus.ACCEPTED

    # Itinerary should NOT have been created
    assert await itin_repo.find_by_trip_id(trip_id) is None
