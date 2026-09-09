"""Sprint 17 — Intelligent Trip Copilot 2.0 Comprehensive Unit Tests."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.application.commands import (
    ChatCommand,
    ConfirmActionCommand,
    RejectActionCommand,
)
from app.modules.travel.assistant.application.services.assistant_context_builder import (
    AssistantContextBuilder,
)
from app.modules.travel.assistant.application.services.assistant_service import (
    AssistantService,
)
from app.modules.travel.assistant.domain.entities.proposed_action import ProposedAction
from app.modules.travel.assistant.domain.enums import (
    ActionStatus,
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.infrastructure.engine.mock_assistant_engine import (
    MockAssistantEngine,
)
from app.modules.travel.itinerary.application.dtos import (
    ItineraryDaySummary,
    ItineraryItemSummary,
    ItinerarySummary,
)
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.weather.domain.provider import WeatherCondition
from app.modules.travel.weather.infrastructure.providers.mock_weather_provider import (
    MockWeatherProvider,
)
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.result import Failure, Success
from app.shared.domain.uuid_provider import StandardUUIDProvider


@pytest.fixture
def sample_user_id() -> UserId:
    return UserId.from_str(str(uuid.uuid4()))


@pytest.fixture
def viewer_user_id() -> UserId:
    return UserId.from_str(str(uuid.uuid4()))


@pytest.fixture
def sample_trip(sample_user_id: UserId) -> Trip:
    return Trip.create(
        trip_id=TripId.from_str(str(uuid.uuid4())),
        owner_id=sample_user_id,
        title=TripTitle("Mysore Heritage & Cultural Tour"),
        privacy=TripPrivacy.PRIVATE,
        date_range=TripDateRange(departure_date=date(2026, 10, 1), return_date=date(2026, 10, 4)),
    )


@pytest.fixture
def mock_weather_provider() -> MockWeatherProvider:
    return MockWeatherProvider(
        default_condition=WeatherCondition.RAIN,
        is_severe=True,
        advisory_msg="Heavy rain advisory for tomorrow",
    )


@pytest.mark.asyncio
async def test_copilot_context_builder_includes_weather_and_routes(
    sample_trip: Trip,
    sample_user_id: UserId,
    mock_weather_provider: MockWeatherProvider,
) -> None:
    """Verify AssistantContextBuilder incorporates weather forecasts, route summaries, and weather warnings."""
    trip_repo = AsyncMock()
    itinerary_repo = AsyncMock()
    budget_repo = AsyncMock()
    collab_repo = AsyncMock()
    collab_repo.find_by_trip_id.return_value = None

    # Setup mock itinerary with outdoor activities
    day_mock = MagicMock()
    day_mock.entity_id = uuid.uuid4()
    day_mock.day_number = 1
    day_mock.title = "Day 1 - Arrival & Palace"
    day_mock.date = date(2026, 10, 1)

    item1 = MagicMock()
    item1.entity_id = uuid.uuid4()
    item1.day_id = day_mock.entity_id
    item1.title.value = "Mysore Palace Outdoor Tour"
    item1.item_type.value = "sightseeing"
    item1.description = "Outdoor garden walk and palace visit"
    item1.start_time = time(10, 0)
    item1.end_time = time(12, 30)
    item1.cost = Decimal("25.00")
    item1.currency = "INR"

    item2 = MagicMock()
    item2.entity_id = uuid.uuid4()
    item2.day_id = day_mock.entity_id
    item2.title.value = "Chamundi Hill Viewpoint"
    item2.item_type.value = "nature"
    item2.description = "Hilltop observation and outdoor temple visit"
    item2.start_time = time(15, 0)
    item2.end_time = time(17, 0)
    item2.cost = Decimal("10.00")
    item2.currency = "INR"

    day_mock.items = [item1, item2]
    itin_mock = MagicMock()
    itin_mock.is_deleted = False
    itin_mock.days = [day_mock]
    itinerary_repo.find_by_trip_id.return_value = itin_mock
    budget_repo.find_by_trip_id.return_value = None

    builder = AssistantContextBuilder(
        trip_repository=trip_repo,
        itinerary_repository=itinerary_repo,
        budget_repository=budget_repo,
        collaboration_repository=collab_repo,
        weather_provider=mock_weather_provider,
    )

    context = await builder.build_context(sample_trip, sample_user_id)

    assert "weather_forecast" in context
    assert context["weather_forecast"]["condition"] == "rain"
    assert context["weather_forecast"]["is_severe"] is True
    assert len(context["route_summary"]) >= 1
    assert context["route_summary"][0]["from_item"] == "Mysore Palace Outdoor Tour"
    assert context["route_summary"][0]["to_item"] == "Chamundi Hill Viewpoint"

    # Weather warning should be flagged for outdoor stops in rain
    weather_warnings = [w for w in context["proactive_warnings"] if w.get("category") == "weather"]
    assert len(weather_warnings) >= 1
    assert "Rain/adverse weather forecast" in weather_warnings[0]["message"]


@pytest.mark.asyncio
async def test_copilot_relax_busy_day_pacing_proposal(
    sample_trip: Trip,
    sample_user_id: UserId,
) -> None:
    """Verify natural-language 'Day 2 is too busy. Make it more relaxed.' generates a pacing proposal."""
    engine = MockAssistantEngine()
    context = {
        "trip": {"title": "Mysore 3-Day Trip"},
        "itinerary": {
            "days": [
                {
                    "day_id": str(uuid.uuid4()),
                    "day_number": 2,
                    "title": "Day 2 - Packed Sightseeing",
                    "items": [
                        {"item_id": str(uuid.uuid4()), "title": "Palace Tour"},
                        {"item_id": str(uuid.uuid4()), "title": "Zoo Visit"},
                        {"item_id": str(uuid.uuid4()), "title": "Market Walk"},
                    ],
                }
            ]
        },
        "budget": {"currency": "INR", "limit": 15000.0, "total_spent": 3000.0},
    }

    result = await engine.chat(
        context=context,
        user_message="Day 2 is too busy. Make it more relaxed.",
    )

    assert result.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.proposed_action is not None
    assert result.proposed_action.action_type == AssistantActionType.PROPOSE_ITINERARY_CHANGE
    assert "2-hour afternoon relaxation window" in result.message
    assert result.proposed_action.payload["rationale"] is not None


@pytest.mark.asyncio
async def test_copilot_replace_activity_nearby_verified_place(
    sample_trip: Trip,
    sample_user_id: UserId,
) -> None:
    """Verify natural-language 'Replace the palace with something nearby.' resolves a nearby verified venue."""
    engine = MockAssistantEngine()
    old_id = str(uuid.uuid4())
    context = {
        "trip": {"title": "Mysore Heritage Tour"},
        "itinerary": {
            "days": [
                {
                    "day_id": str(uuid.uuid4()),
                    "day_number": 1,
                    "title": "Day 1 - City Center",
                    "items": [{"item_id": old_id, "title": "Mysore Palace"}],
                }
            ]
        },
        "budget": {"currency": "INR"},
    }

    result = await engine.chat(
        context=context,
        user_message="Replace the palace with something nearby.",
    )

    assert result.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.proposed_action is not None
    assert result.proposed_action.action_type == AssistantActionType.PROPOSE_REPLACING_ACTIVITY
    assert result.proposed_action.payload["old_item_id"] == old_id
    assert "Jaganmohan Palace Art Gallery" in result.proposed_action.payload["title"]
    assert result.proposed_action.payload["travel_time_impact"] is not None


@pytest.mark.asyncio
async def test_copilot_weather_aware_adaptation_proposal() -> None:
    """Verify 'It's going to rain tomorrow. What should I do?' proposes an indoor sheltered alternative."""
    engine = MockAssistantEngine()
    outdoor_id = str(uuid.uuid4())
    context = {
        "trip": {"title": "Mysore Vacation"},
        "itinerary": {
            "days": [
                {
                    "day_id": str(uuid.uuid4()),
                    "day_number": 2,
                    "title": "Day 2 - Hill & Nature",
                    "items": [{"item_id": outdoor_id, "title": "Chamundi Hills Outdoor Trek"}],
                }
            ]
        },
        "budget": {"currency": "INR"},
    }

    result = await engine.chat(
        context=context,
        user_message="It's going to rain tomorrow. What should I do?",
    )

    assert result.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.proposed_action is not None
    assert result.proposed_action.action_type == AssistantActionType.PROPOSE_REPLACING_ACTIVITY
    assert "Rain Advisory for Day 2" in result.message
    assert result.proposed_action.payload["is_weather_adjustment"] is True
    assert result.proposed_action.payload["item_type"] == "museum"


@pytest.mark.asyncio
async def test_copilot_spend_less_budget_optimization_proposal() -> None:
    """Verify 'Can we spend less tomorrow?' proposes cost-saving activity replacements."""
    engine = MockAssistantEngine()
    item_id = str(uuid.uuid4())
    context = {
        "trip": {"title": "Mysore Trip"},
        "itinerary": {
            "days": [
                {
                    "day_id": str(uuid.uuid4()),
                    "day_number": 2,
                    "title": "Day 2",
                    "items": [{"item_id": item_id, "title": "Luxury Palace Banquet"}],
                }
            ]
        },
        "budget": {"currency": "INR", "limit": 15000.0, "total_spent": 9000.0},
    }

    result = await engine.chat(
        context=context,
        user_message="Can we spend less tomorrow?",
    )

    assert result.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.proposed_action is not None
    assert result.proposed_action.action_type == AssistantActionType.PROPOSE_REPLACING_ACTIVITY
    assert "Historic Heritage Walk" in result.proposed_action.payload["title"]
    assert "Saves approximately" in result.proposed_action.payload["budget_impact"]


@pytest.mark.asyncio
async def test_copilot_move_lunch_reschedule_proposal() -> None:
    """Verify 'Move lunch closer to the next activity.' proposes rescheduling lunch time."""
    engine = MockAssistantEngine()
    lunch_id = str(uuid.uuid4())
    context = {
        "trip": {"title": "Mysore Trip"},
        "itinerary": {
            "days": [
                {
                    "day_id": str(uuid.uuid4()),
                    "day_number": 1,
                    "title": "Day 1",
                    "items": [
                        {"item_id": lunch_id, "title": "Traditional Mysore Lunch"},
                        {"item_id": str(uuid.uuid4()), "title": "Afternoon Guided Tour"},
                    ],
                }
            ]
        },
        "budget": {"currency": "INR"},
    }

    result = await engine.chat(
        context=context,
        user_message="Move lunch closer to the next activity.",
    )

    assert result.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.proposed_action is not None
    assert result.proposed_action.action_type == AssistantActionType.PROPOSE_RESCHEDULING_ACTIVITY
    assert result.proposed_action.payload["start_time"] == "13:00"
    assert result.proposed_action.payload["end_time"] == "14:15"


@pytest.mark.asyncio
async def test_copilot_remove_activity_for_free_time_proposal() -> None:
    """Verify 'Remove the last activity and give me more free time.' targets the day's final scheduled item."""
    engine = MockAssistantEngine()
    item_a_id = str(uuid.uuid4())
    item_b_id = str(uuid.uuid4())
    context = {
        "trip": {"title": "Mysore Trip"},
        "itinerary": {
            "days": [
                {
                    "day_id": str(uuid.uuid4()),
                    "day_number": 1,
                    "title": "Day 1",
                    "items": [
                        {"item_id": item_a_id, "title": "Palace Tour"},
                        {"item_id": item_b_id, "title": "Late Night Sound & Light Show"},
                    ],
                }
            ]
        },
        "budget": {"currency": "INR"},
    }

    result = await engine.chat(
        context=context,
        user_message="Remove the last activity and give me more free time.",
    )

    assert result.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.proposed_action is not None
    assert result.proposed_action.action_type == AssistantActionType.PROPOSE_REMOVING_ACTIVITY
    assert result.proposed_action.payload["item_id"] == item_b_id
    assert "2.5 hours" in result.message
    assert "free time" in result.message


@pytest.mark.asyncio
async def test_copilot_confirm_reschedule_action_execution(
    sample_trip: Trip,
    sample_user_id: UserId,
) -> None:
    """Verify confirm_action atomically applies a PROPOSE_RESCHEDULING_ACTIVITY mutation."""
    action_repo = AsyncMock()
    conv_repo = AsyncMock()
    trip_repo = AsyncMock()
    collab_repo = AsyncMock()
    itin_service = AsyncMock()
    budget_service = AsyncMock()
    budget_repo = AsyncMock()
    uuid_prov = StandardUUIDProvider()

    trip_repo.find_by_id.return_value = sample_trip
    collab_repo.find_by_trip_id.return_value = None

    action_id = uuid.uuid4()
    item_id = str(uuid.uuid4())
    day_id = str(uuid.uuid4())

    proposed = ProposedAction.create(
        action_id=action_id,
        trip_id=sample_trip.trip_id,
        action_type=AssistantActionType.PROPOSE_RESCHEDULING_ACTIVITY,
        summary="Reschedule Lunch",
        description="Moves lunch to 13:00",
        payload={
            "item_id": item_id,
            "day_id": day_id,
            "title": "Lunch at Mylari",
            "start_time": "13:00:00",
            "end_time": "14:15:00",
        },
    )
    action_repo.find_by_id.return_value = proposed

    itin_summary = ItinerarySummary(
        itinerary_id=uuid.uuid4(),
        trip_id=sample_trip.trip_id.value,
        version=2,
        created_at=None,
        updated_at=None,
        deleted_at=None,
        days=[
            ItineraryDaySummary(
                day_id=uuid.UUID(day_id),
                day_number=1,
                title="Day 1",
                date=date(2026, 10, 1),
                created_at=None,
                updated_at=None,
                items=[
                    ItineraryItemSummary(
                        item_id=uuid.UUID(item_id),
                        day_id=uuid.UUID(day_id),
                        title="Lunch at Mylari",
                        item_type="restaurant",
                        description=None,
                        start_time=time(13, 0),
                        end_time=time(14, 15),
                        location_id=None,
                        cost=Decimal("15.00"),
                        currency="INR",
                        created_at=None,
                        updated_at=None,
                    )
                ],
            )
        ],
    )
    itin_service.update_item.return_value = Success(itin_summary)

    service = AssistantService(
        assistant_engine=MockAssistantEngine(),
        context_builder=AsyncMock(),
        action_repository=action_repo,
        conversation_repository=conv_repo,
        trip_repository=trip_repo,
        collaboration_repository=collab_repo,
        itinerary_service=itin_service,
        budget_service=budget_service,
        budget_repository=budget_repo,
        uuid_provider=uuid_prov,
    )

    cmd = ConfirmActionCommand(
        trip_id=str(sample_trip.trip_id),
        action_id=str(action_id),
        requester_id=str(sample_user_id),
    )

    result = await service.confirm_action(cmd)

    assert isinstance(result, Success)
    assert result.value.action.status == ActionStatus.APPLIED
    assert itin_service.update_item.called
    assert action_repo.save.called


@pytest.mark.asyncio
async def test_copilot_confirm_replace_activity_execution(
    sample_trip: Trip,
    sample_user_id: UserId,
) -> None:
    """Verify confirm_action atomically executes PROPOSE_REPLACING_ACTIVITY (remove old + add new)."""
    action_repo = AsyncMock()
    conv_repo = AsyncMock()
    trip_repo = AsyncMock()
    collab_repo = AsyncMock()
    itin_service = AsyncMock()
    budget_service = AsyncMock()
    budget_repo = AsyncMock()
    uuid_prov = StandardUUIDProvider()

    trip_repo.find_by_id.return_value = sample_trip
    collab_repo.find_by_trip_id.return_value = None

    action_id = uuid.uuid4()
    old_id = str(uuid.uuid4())
    day_id = str(uuid.uuid4())

    proposed = ProposedAction.create(
        action_id=action_id,
        trip_id=sample_trip.trip_id,
        action_type=AssistantActionType.PROPOSE_REPLACING_ACTIVITY,
        summary="Replace with Art Gallery",
        description="Replaces palace with art gallery",
        payload={
            "old_item_id": old_id,
            "day_id": day_id,
            "title": "Jaganmohan Palace Art Gallery",
            "item_type": "museum",
            "start_time": "11:00:00",
            "end_time": "13:00:00",
            "cost": "20.00",
        },
    )
    action_repo.find_by_id.return_value = proposed
    itin_service.remove_item.return_value = Success(None)
    itin_service.add_item.return_value = Success(MagicMock())

    service = AssistantService(
        assistant_engine=MockAssistantEngine(),
        context_builder=AsyncMock(),
        action_repository=action_repo,
        conversation_repository=conv_repo,
        trip_repository=trip_repo,
        collaboration_repository=collab_repo,
        itinerary_service=itin_service,
        budget_service=budget_service,
        budget_repository=budget_repo,
        uuid_provider=uuid_prov,
    )

    cmd = ConfirmActionCommand(
        trip_id=str(sample_trip.trip_id),
        action_id=str(action_id),
        requester_id=str(sample_user_id),
    )

    result = await service.confirm_action(cmd)

    assert isinstance(result, Success)
    assert result.value.action.status == ActionStatus.APPLIED
    assert itin_service.remove_item.called
    assert itin_service.add_item.called


@pytest.mark.asyncio
async def test_copilot_viewer_role_rejected_from_confirming(
    sample_trip: Trip,
    viewer_user_id: UserId,
) -> None:
    """Verify users with VIEWER role are strictly rejected from confirming mutations (403 Forbidden)."""
    action_repo = AsyncMock()
    conv_repo = AsyncMock()
    trip_repo = AsyncMock()
    collab_repo = AsyncMock()
    itin_service = AsyncMock()
    budget_service = AsyncMock()
    budget_repo = AsyncMock()
    uuid_prov = StandardUUIDProvider()

    trip_repo.find_by_id.return_value = sample_trip

    # Setup viewer role in collaboration repo
    collab_mock = MagicMock()
    member_mock = MagicMock()
    member_mock.user_id = viewer_user_id
    member_mock.role.value = "viewer"
    collab_mock.members = [member_mock]
    collab_repo.find_by_trip_id.return_value = collab_mock

    action_id = uuid.uuid4()
    proposed = ProposedAction.create(
        action_id=action_id,
        trip_id=sample_trip.trip_id,
        action_type=AssistantActionType.PROPOSE_REMOVING_ACTIVITY,
        summary="Remove item",
        description="desc",
        payload={"item_id": str(uuid.uuid4())},
    )
    action_repo.find_by_id.return_value = proposed

    service = AssistantService(
        assistant_engine=MockAssistantEngine(),
        context_builder=AsyncMock(),
        action_repository=action_repo,
        conversation_repository=conv_repo,
        trip_repository=trip_repo,
        collaboration_repository=collab_repo,
        itinerary_service=itin_service,
        budget_service=budget_service,
        budget_repository=budget_repo,
        uuid_provider=uuid_prov,
    )

    cmd = ConfirmActionCommand(
        trip_id=str(sample_trip.trip_id),
        action_id=str(action_id),
        requester_id=str(viewer_user_id),
    )

    result = await service.confirm_action(cmd)

    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)
    assert "Viewers are not permitted" in str(result.error.message)


@pytest.mark.asyncio
async def test_copilot_reject_action_marks_rejected_and_non_mutating(
    sample_trip: Trip,
    sample_user_id: UserId,
) -> None:
    """Verify reject_action marks proposal as REJECTED without modifying itinerary or budget."""
    action_repo = AsyncMock()
    conv_repo = AsyncMock()
    trip_repo = AsyncMock()
    collab_repo = AsyncMock()
    itin_service = AsyncMock()
    budget_service = AsyncMock()
    budget_repo = AsyncMock()
    uuid_prov = StandardUUIDProvider()

    trip_repo.find_by_id.return_value = sample_trip
    collab_repo.find_by_trip_id.return_value = None

    action_id = uuid.uuid4()
    proposed = ProposedAction.create(
        action_id=action_id,
        trip_id=sample_trip.trip_id,
        action_type=AssistantActionType.PROPOSE_REMOVING_ACTIVITY,
        summary="Remove activity",
        description="desc",
        payload={"item_id": str(uuid.uuid4())},
    )
    action_repo.find_by_id.return_value = proposed

    service = AssistantService(
        assistant_engine=MockAssistantEngine(),
        context_builder=AsyncMock(),
        action_repository=action_repo,
        conversation_repository=conv_repo,
        trip_repository=trip_repo,
        collaboration_repository=collab_repo,
        itinerary_service=itin_service,
        budget_service=budget_service,
        budget_repository=budget_repo,
        uuid_provider=uuid_prov,
    )

    cmd = RejectActionCommand(
        trip_id=str(sample_trip.trip_id),
        action_id=str(action_id),
        requester_id=str(sample_user_id),
    )

    result = await service.reject_action(cmd)

    assert isinstance(result, Success)
    assert result.value.action.status == ActionStatus.REJECTED
    assert action_repo.save.called
    assert not itin_service.remove_item.called
    assert not itin_service.add_item.called
