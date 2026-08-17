"""Unit tests for the TripProposal domain aggregate."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.planning.domain.entities.trip_proposal import TripProposal
from app.modules.travel.planning.domain.errors import (
    InvalidProposalStatusTransitionError,
    ProposalAlreadyDeletedError,
)
from app.modules.travel.planning.domain.events.proposal_events import (
    ProposalAccepted,
    ProposalFailed,
    ProposalGenerationStarted,
    ProposalReady,
    ProposalRejected,
    ProposalRequested,
)
from app.modules.travel.planning.domain.value_objects.planning_preferences import (
    PlanningPreferences,
)
from app.modules.travel.planning.domain.value_objects.planning_result import (
    PlanningResult,
)
from app.modules.travel.planning.domain.value_objects.proposal_id import ProposalId
from app.modules.travel.planning.domain.value_objects.proposal_status import (
    ProposalStatus,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


def _make_preferences() -> PlanningPreferences:
    return PlanningPreferences(
        destination="Rome",
        duration_days=3,
        budget_level="mid_range",
        interests=("history", "art"),
        travel_style="balanced",
        special_requirements="",
    )


def _make_proposal() -> TripProposal:
    return TripProposal.create(
        proposal_id=ProposalId(value=uuid.uuid4()),
        trip_id=TripId(value=uuid.uuid4()),
        owner_id=UserId(value=uuid.uuid4()),
        preferences=_make_preferences(),
    )


def test_create_sets_queued_status() -> None:
    proposal = _make_proposal()
    assert proposal.status == ProposalStatus.QUEUED
    assert proposal.version == 1
    assert proposal.is_deleted is False


def test_create_emits_proposal_requested_event() -> None:
    proposal = _make_proposal()
    events = proposal.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], ProposalRequested)


def test_start_generation_transitions_to_generating() -> None:
    proposal = _make_proposal()
    proposal.pop_events()  # Clear creation event
    proposal.start_generation()
    assert proposal.status == ProposalStatus.GENERATING
    assert proposal.version == 2

    events = proposal.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], ProposalGenerationStarted)


def test_invalid_transition_raises_error() -> None:
    proposal = _make_proposal()
    # Cannot go directly from QUEUED to READY
    with pytest.raises(InvalidProposalStatusTransitionError):
        result = PlanningResult(
            summary="Rome plan", days=(), estimated_total_cost=None, generated_at=datetime.now(UTC)
        )
        proposal.complete_generation(result, datetime.now(UTC))


def test_complete_generation_transitions_to_ready() -> None:
    proposal = _make_proposal()
    proposal.start_generation()
    proposal.pop_events()

    result = PlanningResult(
        summary="Rome plan", days=(), estimated_total_cost="$195", generated_at=datetime.now(UTC)
    )
    expires_at = datetime.now(UTC) + timedelta(hours=24)
    proposal.complete_generation(result, expires_at)

    assert proposal.status == ProposalStatus.READY
    assert proposal.result == result
    assert proposal.expires_at == expires_at
    assert proposal.version == 3

    events = proposal.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], ProposalReady)


def test_accept_proposal_succeeds() -> None:
    proposal = _make_proposal()
    proposal.start_generation()
    result = PlanningResult(
        summary="Rome plan", days=(), estimated_total_cost="$195", generated_at=datetime.now(UTC)
    )
    proposal.complete_generation(result, datetime.now(UTC) + timedelta(hours=24))
    proposal.pop_events()

    proposal.accept()
    assert proposal.status == ProposalStatus.ACCEPTED

    events = proposal.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], ProposalAccepted)


def test_reject_proposal_succeeds() -> None:
    proposal = _make_proposal()
    proposal.start_generation()
    result = PlanningResult(
        summary="Rome plan", days=(), estimated_total_cost="$195", generated_at=datetime.now(UTC)
    )
    proposal.complete_generation(result, datetime.now(UTC) + timedelta(hours=24))
    proposal.pop_events()

    proposal.reject()
    assert proposal.status == ProposalStatus.REJECTED

    events = proposal.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], ProposalRejected)


def test_fail_proposal_succeeds() -> None:
    proposal = _make_proposal()
    proposal.start_generation()
    proposal.pop_events()

    proposal.fail("AI service timed out")
    assert proposal.status == ProposalStatus.FAILED
    assert proposal.failure_reason == "AI service timed out"

    events = proposal.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], ProposalFailed)


def test_lazy_expiry_precludes_acceptance() -> None:
    proposal = _make_proposal()
    proposal.start_generation()
    result = PlanningResult(
        summary="Rome plan", days=(), estimated_total_cost="$195", generated_at=datetime.now(UTC)
    )
    # Expired 1 hour ago
    proposal.complete_generation(result, datetime.now(UTC) - timedelta(hours=1))

    assert proposal.is_expired is True

    # Try to accept -> should transition to EXPIRED and raise InvalidProposalStatusTransitionError
    with pytest.raises(InvalidProposalStatusTransitionError):
        proposal.accept()

    assert proposal.status == ProposalStatus.EXPIRED


def test_mutation_on_deleted_proposal_raises_error() -> None:
    proposal = _make_proposal()
    proposal.delete()

    with pytest.raises(ProposalAlreadyDeletedError):
        proposal.start_generation()
