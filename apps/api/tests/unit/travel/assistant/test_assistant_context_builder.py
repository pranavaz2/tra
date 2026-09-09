"""Unit tests for AssistantContextBuilder."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.application.services.assistant_context_builder import (
    AssistantContextBuilder,
)
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.sharing.domain.entities.trip_collaboration import (
    TripCollaboration,
)
from app.modules.travel.sharing.domain.entities.trip_member import TripMember
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.value_objects.collaboration_id import (
    CollaborationId,
)
from app.modules.travel.sharing.domain.value_objects.member_id import MemberId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class MockTripRepo:
    def __init__(self, trip: Trip | None = None) -> None:
        self.trip = trip

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self.trip


class MockItineraryRepo:
    def __init__(self, itinerary: Itinerary | None = None) -> None:
        self.itinerary = itinerary

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        return self.itinerary


class MockBudgetRepo:
    def __init__(self, budget: TripBudget | None = None) -> None:
        self.budget = budget

    async def find_by_trip_id(self, trip_id: TripId) -> TripBudget | None:
        return self.budget


class MockCollabRepo:
    def __init__(self, collab: TripCollaboration | None = None) -> None:
        self.collab = collab

    async def find_by_trip_id(self, trip_id: TripId) -> TripCollaboration | None:
        return self.collab


@pytest.mark.asyncio
async def test_assistant_context_builder_for_owner() -> None:
    owner_id = UserId(value=uuid.uuid4())
    trip_id = TripId(value=uuid.uuid4())

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle(value="Tokyo Gourmet Expedition"),
        date_range=TripDateRange(departure_date=date(2026, 10, 1), return_date=date(2026, 10, 7)),
        privacy=TripPrivacy.PRIVATE,
    )

    itinerary = Itinerary.create(
        itinerary_id=ItineraryId(value=uuid.uuid4()),
        trip_id=trip_id,
    )
    itinerary.add_day(
        day_id=ItineraryDayId(value=uuid.uuid4()),
        day_number=1,
        title="Arrival in Shibuya",
        date=date(2026, 10, 1),
    )
    itinerary.add_item(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=itinerary.days[0].entity_id,
        title=ItemTitle(value="Ramen Tasting"),
        item_type=ItineraryItemType.ACTIVITY,
        cost=Decimal("25.00"),
        currency="USD",
    )

    from app.modules.travel.budget.domain.value_objects.money import Money

    budget = TripBudget.create(
        budget_id=BudgetId(value=uuid.uuid4()),
        trip_id=trip_id,
        owner_id=owner_id,
        limit=Money(amount=Decimal("3000.00"), currency="USD"),
    )

    builder = AssistantContextBuilder(
        trip_repository=MockTripRepo(trip),
        itinerary_repository=MockItineraryRepo(itinerary),
        budget_repository=MockBudgetRepo(budget),
        collaboration_repository=MockCollabRepo(None),
    )

    context = await builder.build_context(trip, owner_id)

    assert context["user_role"] == "owner"
    assert context["trip"]["title"] == "Tokyo Gourmet Expedition"
    assert len(context["itinerary"]["days"]) == 1
    assert context["itinerary"]["days"][0]["title"] == "Arrival in Shibuya"
    assert len(context["itinerary"]["days"][0]["items"]) == 1
    assert context["budget"]["has_budget"] is True
    assert context["budget"]["limit"] == 3000.0


@pytest.mark.asyncio
async def test_assistant_context_builder_for_collaborator_viewer() -> None:
    owner_id = UserId(value=uuid.uuid4())
    viewer_id = UserId(value=uuid.uuid4())
    trip_id = TripId(value=uuid.uuid4())

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle(value="Paris Vacation"),
        date_range=None,
    )

    collab = TripCollaboration.create(
        collaboration_id=CollaborationId(value=uuid.uuid4()),
        trip_id=trip_id,
        owner_id=owner_id,
        owner_member_id=MemberId(value=uuid.uuid4()),
    )
    collab.members.append(
        TripMember(
            entity_id=MemberId(value=uuid.uuid4()),
            user_id=viewer_id,
            role=MemberRole.VIEWER,
        )
    )

    builder = AssistantContextBuilder(
        trip_repository=MockTripRepo(trip),
        itinerary_repository=MockItineraryRepo(None),
        budget_repository=MockBudgetRepo(None),
        collaboration_repository=MockCollabRepo(collab),
    )

    context = await builder.build_context(trip, viewer_id)

    assert context["user_role"] == "viewer"
    assert context["trip"]["title"] == "Paris Vacation"
    assert context["budget"]["has_budget"] is False
    assert len(context["itinerary"]["days"]) == 0
