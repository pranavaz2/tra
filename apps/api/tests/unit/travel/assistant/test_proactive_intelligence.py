"""Unit tests for Proactive Travel Intelligence (Sprint 12)."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
import uuid
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.locations.models import Location, LocationType
from app.modules.travel.assistant.application.dtos import (
    TripWarningsDTO,
)
from app.modules.travel.assistant.application.services.assistant_context_builder import (
    AssistantContextBuilder,
)
from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
    ProactiveIntelligenceService,
    haversine_distance_km,
)
from app.modules.travel.assistant.domain.enums import (
    AssistantActionType,
    WarningCategory,
    WarningSeverity,
)
from app.modules.travel.assistant.infrastructure.engine.mock_assistant_engine import (
    MockAssistantEngine,
)
from app.modules.travel.budget.domain.entities.budget_category import BudgetCategory
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.itinerary.domain.entities.day import ItineraryDay
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle


# In-memory mock repositories
class _InMemoryItineraryRepository:
    def __init__(self, itinerary: Itinerary | None = None) -> None:
        self._itinerary = itinerary

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        if self._itinerary and self._itinerary.trip_id == trip_id:
            return self._itinerary
        return None


class _InMemoryBudgetRepository:
    def __init__(self, budget: TripBudget | None = None) -> None:
        self._budget = budget

    async def find_by_trip_id(self, trip_id: TripId) -> TripBudget | None:
        if self._budget and self._budget.trip_id == trip_id:
            return self._budget
        return None


class _MockLocationRepo:
    def __init__(self, locations: dict[uuid.UUID, Location] | None = None) -> None:
        self._locations = locations or {}

    async def get_by_id(self, location_id: uuid.UUID) -> Location | None:
        return self._locations.get(location_id)


def _make_location(
    loc_id: uuid.UUID, name: str, lat: float, lon: float
) -> Location:
    loc = Location()
    loc.id = loc_id
    loc.name = name
    loc.slug = name.lower().replace(" ", "-")
    loc.location_type = LocationType.PLACE
    loc.country_code = "US"
    loc.latitude = Decimal(str(lat))
    loc.longitude = Decimal(str(lon))
    return loc


def _make_itinerary(trip_id: TripId, days: list[ItineraryDay]) -> Itinerary:
    return Itinerary(
        entity_id=ItineraryId(value=uuid.uuid4()),
        trip_id=trip_id,
        version=1,
        days=days,
    )


def _make_item(
    day_id: ItineraryDayId,
    title: str,
    start_time: time | None = None,
    end_time: time | None = None,
    location_id: uuid.UUID | None = None,
) -> ItineraryItem:
    return ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value=title),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=start_time,
        end_time=end_time,
        location_id=location_id,
    )



@pytest.mark.asyncio
async def test_haversine_distance_calculation():
    # NYC (Times Square: 40.7580, -73.9855) to Brooklyn Bridge (40.7061, -73.9969) ~ 5.8 km
    dist = haversine_distance_km(40.7580, -73.9855, 40.7061, -73.9969)
    assert 5.0 < dist < 7.0


@pytest.mark.asyncio
async def test_detect_overlapping_activities_same_day():
    trip_id = TripId(value=uuid.uuid4())
    itin_id = ItineraryId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())

    item1 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Museum Visit"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(10, 0),
        end_time=time(12, 0),
    )
    item2 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Lunch Reservation"),
        item_type=ItineraryItemType.RESTAURANT,
        start_time=time(11, 30),
        end_time=time(13, 0),
    )

    day = ItineraryDay.create(
        day_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        version=1,
        days=[day],
    )

    itin_repo = _InMemoryItineraryRepository(itinerary)
    budget_repo = _InMemoryBudgetRepository(None)
    service = ProactiveIntelligenceService(
        itinerary_repository=itin_repo, budget_repository=budget_repo
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    assert len(warnings) >= 1
    overlap_w = next((w for w in warnings if w.category == WarningCategory.TIMING and "overlap" in w.warning_id), None)
    assert overlap_w is not None
    assert overlap_w.severity == WarningSeverity.WARNING
    assert overlap_w.day_number == 1
    assert "Museum Visit" in overlap_w.message
    assert "Lunch Reservation" in overlap_w.message


@pytest.mark.asyncio
async def test_detect_invalid_activity_times_end_before_start():
    trip_id = TripId(value=uuid.uuid4())
    itin_id = ItineraryId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())

    item = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Night Tour"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(20, 0),
        end_time=time(19, 0),  # invalid end before start!
    )

    day = ItineraryDay.create(
        day_id=day_id,
        itinerary_id=itin_id,
        day_number=2,
        title="Day 2",
        items=[item],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        version=1,
        days=[day],
    )

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.severity == WarningSeverity.CRITICAL
    assert w.category == WarningCategory.TIMING
    assert "earlier than or equal to its start time" in w.message
    assert w.day_number == 2


@pytest.mark.asyncio
async def test_detect_insufficient_transit_gap_between_activities():
    trip_id = TripId(value=uuid.uuid4())
    itin_id = ItineraryId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())

    item1 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Morning Walk"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(9, 0),
        end_time=time(10, 0),
    )
    item2 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Coffee Tasting"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(10, 5),  # 5 min gap
        end_time=time(10, 45),
    )

    day = ItineraryDay.create(
        day_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        version=1,
        days=[day],
    )

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    gap_w = next((w for w in warnings if "insufficient_gap" in w.warning_id), None)
    assert gap_w is not None
    assert "5 minutes" in gap_w.message
    assert "Morning Walk" in gap_w.message


@pytest.mark.asyncio
async def test_detect_unrealistic_distance_between_verified_places():
    trip_id = TripId(value=uuid.uuid4())
    itin_id = ItineraryId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())

    loc_id1 = uuid.uuid4()
    loc_id2 = uuid.uuid4()

    # Place 1: Central Paris (48.8566, 2.3522)
    # Place 2: Versailles (~ 17 km away: 48.8049, 2.1204)
    loc1 = _make_location(loc_id1, "Louvre Museum", 48.8566, 2.3522)
    loc2 = _make_location(loc_id2, "Palace of Versailles", 48.8049, 2.1204)

    loc_repo = _MockLocationRepo({loc_id1: loc1, loc_id2: loc2})

    item1 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Louvre Museum Tour"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(10, 0),
        end_time=time(12, 0),
        location_id=loc_id1,
    )
    item2 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Versailles Gardens Walk"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=time(12, 15),  # only 15 min for 17 km!
        end_time=time(14, 0),
        location_id=loc_id2,
    )

    day = ItineraryDay.create(
        day_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        version=1,
        days=[day],
    )

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
        location_repository=loc_repo,
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    dist_w = next((w for w in warnings if w.category == WarningCategory.DISTANCE), None)
    assert dist_w is not None
    assert dist_w.severity == WarningSeverity.WARNING
    assert "15 minutes" in dist_w.message
    assert "approximately" in dist_w.message
    assert dist_w.metadata.get("is_verified_coordinates") is True
    assert dist_w.metadata.get("estimated_distance_km") > 15.0


@pytest.mark.asyncio
async def test_missing_coordinates_and_times_handled_safely():
    trip_id = TripId(value=uuid.uuid4())
    itin_id = ItineraryId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())

    # Items with no times or no location_id
    item1 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Explore City"),
        item_type=ItineraryItemType.ACTIVITY,
        start_time=None,
        end_time=None,
    )
    item2 = ItineraryItem.create(
        item_id=ItineraryItemId(value=uuid.uuid4()),
        day_id=day_id,
        title=ItemTitle(value="Dinner"),
        item_type=ItineraryItemType.RESTAURANT,
        start_time=time(19, 0),
        end_time=None,
    )

    day = ItineraryDay.create(
        day_id=day_id,
        itinerary_id=itin_id,
        day_number=1,
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = Itinerary(
        entity_id=itin_id,
        trip_id=trip_id,
        version=1,
        days=[day],
    )

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    # No timing/distance conflicts should occur
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_empty_itinerary_produces_no_warnings():
    trip_id = TripId(value=uuid.uuid4())
    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(None),
        budget_repository=_InMemoryBudgetRepository(None),
    )
    warnings = await service.evaluate_trip_warnings(trip_id)
    assert warnings == []


@pytest.mark.asyncio
async def test_detect_total_budget_limit_overage():
    trip_id = TripId(value=uuid.uuid4())
    user_id = UserId(value=uuid.uuid4())
    budget_id = BudgetId(value=uuid.uuid4())
    cat_id = CategoryId(value=uuid.uuid4())

    category = BudgetCategory(
        entity_id=cat_id,
        name="Dining",
    )
    expense1 = Expense(
        entity_id=ExpenseId(value=uuid.uuid4()),
        category_id=cat_id,
        title="Dinner A",
        amount=Money(Decimal("600.00"), "USD"),
        expense_type=ExpenseType.RESTAURANT,
        expense_date=date.today(),
    )
    expense2 = Expense(
        entity_id=ExpenseId(value=uuid.uuid4()),
        category_id=cat_id,
        title="Dinner B",
        amount=Money(Decimal("500.00"), "USD"),
        expense_type=ExpenseType.RESTAURANT,
        expense_date=date.today(),
    )

    budget = TripBudget.create(
        budget_id=budget_id,
        trip_id=trip_id,
        owner_id=user_id,
        limit=Money(Decimal("1000.00"), "USD"),
    )
    budget.categories = [category]
    budget.expenses = [expense1, expense2]

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(None),
        budget_repository=_InMemoryBudgetRepository(budget),
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    budget_w = next((w for w in warnings if w.category == WarningCategory.BUDGET and "budget_overage" in w.warning_id), None)
    assert budget_w is not None
    assert budget_w.severity == WarningSeverity.CRITICAL
    assert "Trip budget exceeded" in budget_w.message
    assert "1100.00" in budget_w.message


@pytest.mark.asyncio
async def test_detect_category_allocation_overage():
    trip_id = TripId(value=uuid.uuid4())
    user_id = UserId(value=uuid.uuid4())
    budget_id = BudgetId(value=uuid.uuid4())
    cat_id = CategoryId(value=uuid.uuid4())

    category = BudgetCategory(
        entity_id=cat_id,
        name="Transport",
    )
    category.allocated_amount = Money(Decimal("100.00"), "USD")  # type: ignore

    expense = Expense(
        entity_id=ExpenseId(value=uuid.uuid4()),
        category_id=cat_id,
        title="Taxi",
        amount=Money(Decimal("150.00"), "USD"),
        expense_type=ExpenseType.TRANSPORT,
        expense_date=date.today(),
    )

    budget = TripBudget.create(
        budget_id=budget_id,
        trip_id=trip_id,
        owner_id=user_id,
        limit=Money(Decimal("2000.00"), "USD"),
    )
    budget.categories = [category]
    budget.expenses = [expense]

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(None),
        budget_repository=_InMemoryBudgetRepository(budget),
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    cat_w = next((w for w in warnings if w.category == WarningCategory.BUDGET and "category_overage" in w.warning_id), None)
    assert cat_w is not None
    assert cat_w.severity == WarningSeverity.WARNING
    assert "Transport" in cat_w.message
    assert "150.00" in cat_w.message


@pytest.mark.asyncio
async def test_mock_assistant_engine_handles_proactive_intelligence_queries():
    engine = MockAssistantEngine()
    trip_id = str(uuid.uuid4())

    # Context with proactive warning
    context = {
        "trip": {"title": "Tokyo Adventure"},
        "itinerary": {"days": []},
        "budget": {"currency": "USD"},
        "proactive_warnings": [
            {
                "warning_id": "overlap_1_2",
                "category": "timing",
                "severity": "warning",
                "title": "Schedule Overlap",
                "message": "Activities 'Team Meeting' and 'Lunch' overlap on Day 1.",
            }
        ],
    }

    # 1. Ask about schedule conflicts
    result = await engine.chat(
        context=context,
        user_message="Check itinerary conflicts please",
    )
    assert result.response_type.value == "informational"
    assert AssistantActionType.CHECK_ITINERARY_CONFLICTS in result.tools_used
    assert "Team Meeting" in result.message

    # 2. Ask about travel feasibility
    result_feasibility = await engine.chat(
        context=context,
        user_message="Check travel feasibility",
    )
    assert AssistantActionType.CHECK_TRAVEL_FEASIBILITY in result_feasibility.tools_used

    # 3. Ask about budget risks
    result_budget = await engine.chat(
        context=context,
        user_message="Check budget risks",
    )
    assert AssistantActionType.CHECK_BUDGET_RISKS in result_budget.tools_used


@pytest.mark.asyncio
async def test_real_routing_insufficient_travel_time_warning():
    from app.services.maps.mock import MockRoutingProvider
    from app.services.maps.route import RouteDetails, TravelMode

    trip_id = TripId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())
    loc1_id = uuid.uuid4()
    loc2_id = uuid.uuid4()

    loc1 = _make_location(loc1_id, "Eiffel Tower", 48.8584, 2.2945)
    loc2 = _make_location(loc2_id, "Versailles Palace", 48.8049, 2.1204)

    # Activities scheduled with only 15 minutes gap
    item1 = _make_item(day_id, "Eiffel Tower", time(9, 0), time(11, 0), location_id=loc1_id)
    item2 = _make_item(day_id, "Versailles Palace", time(11, 15), time(14, 0), location_id=loc2_id)

    day = ItineraryDay(
        entity_id=day_id,
        itinerary_id=ItineraryId(value=uuid.uuid4()),
        day_number=1,
        date=date(2026, 6, 1),
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = _make_itinerary(trip_id, [day])

    # Routing provider returns 34 minutes drive time
    routing = MockRoutingProvider()
    routing.register_route(
        (48.8584, 2.2945),
        (48.8049, 2.1204),
        RouteDetails(
            origin_coordinates=(48.8584, 2.2945),
            destination_coordinates=(48.8049, 2.1204),
            distance_meters=18500,
            duration_seconds=2040,  # 34 minutes
            travel_mode=TravelMode.DRIVE.value,
        ),
    )

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
        location_repository=_MockLocationRepo({loc1_id: loc1, loc2_id: loc2}),
        routing_provider=routing,
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.category == WarningCategory.DISTANCE
    assert w.severity in (WarningSeverity.WARNING, WarningSeverity.CRITICAL)
    assert "Insufficient Travel Time" in w.title

    assert "Only 15 minutes between these activities" in w.message
    assert "estimated drive time is 34 minutes" in w.message
    assert w.metadata["estimated_duration_minutes"] == 34
    assert w.metadata["route_distance_km"] == 18.5
    assert w.metadata["travel_mode"] == "drive"
    assert w.metadata["gap_minutes"] == 15


@pytest.mark.asyncio
async def test_real_routing_adequate_travel_time_no_warning():
    from app.services.maps.mock import MockRoutingProvider
    from app.services.maps.route import RouteDetails, TravelMode

    trip_id = TripId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())
    loc1_id = uuid.uuid4()
    loc2_id = uuid.uuid4()

    loc1 = _make_location(loc1_id, "Colosseum", 41.8902, 12.4922)
    loc2 = _make_location(loc2_id, "Trattoria Da Enzo", 41.8875, 12.4772)

    # 45 minutes gap between activities with only 8 mins drive time
    item1 = _make_item(day_id, "Colosseum Visit", time(9, 0), time(11, 0), location_id=loc1_id)
    item2 = _make_item(day_id, "Lunch Da Enzo", time(11, 45), time(13, 0), location_id=loc2_id)

    day = ItineraryDay(
        entity_id=day_id,
        itinerary_id=ItineraryId(value=uuid.uuid4()),
        day_number=1,
        date=date(2026, 6, 1),
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = _make_itinerary(trip_id, [day])

    routing = MockRoutingProvider()
    routing.register_route(
        (41.8902, 12.4922),
        (41.8875, 12.4772),
        RouteDetails(
            origin_coordinates=(41.8902, 12.4922),
            destination_coordinates=(41.8875, 12.4772),
            distance_meters=2100,
            duration_seconds=480,  # 8 minutes
            travel_mode=TravelMode.DRIVE.value,
        ),
    )

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
        location_repository=_MockLocationRepo({loc1_id: loc1, loc2_id: loc2}),
        routing_provider=routing,
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    # No conflict or travel feasibility warnings should be emitted
    assert len(warnings) == 0


@pytest.mark.asyncio
async def test_routing_provider_failure_gracefully_falls_back_to_haversine():
    from app.services.maps.mock import MockRoutingProvider

    trip_id = TripId(value=uuid.uuid4())
    day_id = ItineraryDayId(value=uuid.uuid4())
    loc1_id = uuid.uuid4()
    loc2_id = uuid.uuid4()

    loc1 = _make_location(loc1_id, "Rome Center", 41.9028, 12.4964)
    loc2 = _make_location(loc2_id, "Ostia Beach", 41.7317, 12.2858)  # ~25 km away

    # 10 minutes gap for 25km distance
    item1 = _make_item(day_id, "Rome Tour", time(9, 0), time(11, 0), location_id=loc1_id)
    item2 = _make_item(day_id, "Beach Relax", time(11, 10), time(14, 0), location_id=loc2_id)

    day = ItineraryDay(
        entity_id=day_id,
        itinerary_id=ItineraryId(value=uuid.uuid4()),
        day_number=1,
        date=date(2026, 6, 1),
        title="Day 1",
        items=[item1, item2],
    )
    itinerary = _make_itinerary(trip_id, [day])

    # Routing provider configured to simulate an unexpected failure
    failing_routing = MockRoutingProvider(simulate_failure=True)

    service = ProactiveIntelligenceService(
        itinerary_repository=_InMemoryItineraryRepository(itinerary),
        budget_repository=_InMemoryBudgetRepository(None),
        location_repository=_MockLocationRepo({loc1_id: loc1, loc2_id: loc2}),
        routing_provider=failing_routing,
    )

    warnings = await service.evaluate_trip_warnings(trip_id)
    assert len(warnings) == 1
    w = warnings[0]
    assert w.category == WarningCategory.DISTANCE
    assert "Tight Travel Feasibility" in w.title
    assert w.metadata.get("is_fallback") is True


@pytest.mark.asyncio
async def test_assistant_engine_route_estimation_query():
    engine = MockAssistantEngine()

    context = {
        "trip": {"title": "Rome Adventure"},
        "itinerary": {
            "days": [
                {
                    "day_number": 1,
                    "items": [
                        {"title": "Colosseum", "location_id": str(uuid.uuid4())},
                        {"title": "Trattoria Da Enzo", "location_id": str(uuid.uuid4())},
                    ],
                }
            ]
        },
        "budget": {"currency": "EUR"},
    }

    result = await engine.chat(
        context=context,
        user_message="How long will it take to travel from Colosseum to Trattoria Da Enzo?",
    )

    assert result.response_type.value == "informational"
    assert AssistantActionType.ESTIMATE_TRAVEL_TIME in result.tools_used
    assert AssistantActionType.CHECK_ROUTE_BETWEEN_ACTIVITIES in result.tools_used
    assert "Route Analysis" in result.message
    assert "Colosseum" in result.message
    assert "Trattoria Da Enzo" in result.message

