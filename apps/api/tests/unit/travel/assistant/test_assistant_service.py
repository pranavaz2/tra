"""Unit tests for AssistantService (Sprint 10: Multi-Turn Memory + Budget AI Tools)."""

from __future__ import annotations

from decimal import Decimal
import uuid
from datetime import UTC, date, datetime
import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.application.commands import (
    ChatCommand,
    ClearHistoryCommand,
    ConfirmActionCommand,
    GetHistoryQuery,
    RejectActionCommand,
)
from app.modules.travel.assistant.application.services.assistant_context_builder import (
    AssistantContextBuilder,
)
from app.modules.travel.assistant.application.services.assistant_service import (
    AssistantService,
)
from app.modules.travel.assistant.domain.enums import (
    ActionStatus,
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.domain.errors import (
    ActionAlreadyExecutedError,
    ProposedActionNotFoundError,
)
from app.modules.travel.assistant.infrastructure.engine.mock_assistant_engine import (
    MockAssistantEngine,
)
from app.modules.travel.assistant.infrastructure.repositories.conversation_repository_impl import (
    InMemoryAssistantConversationRepository,
)
from app.modules.travel.assistant.infrastructure.repositories.in_memory_action_repo import (
    InMemoryProposedActionRepository,
)
from app.modules.travel.budget.application.budget_service import BudgetService
from app.modules.travel.budget.domain.entities.budget_category import BudgetCategory
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.money import Money

from app.modules.travel.itinerary.application.itinerary_service import ItineraryService
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)

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
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.clock import SystemClock
from app.shared.domain.errors import ForbiddenError
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider


class SimpleMockUoW(UnitOfWork):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def commit(self):
        pass

    async def rollback(self):
        pass


class SimpleMockEventPublisher:
    async def publish(self, events):
        pass


class SimpleTripRepo:
    def __init__(self, trip: Trip | None = None):
        self._trips = {str(trip.trip_id): trip} if trip else {}

    async def find_by_id(self, trip_id: TripId):
        return self._trips.get(str(trip_id))

    async def save(self, trip: Trip):
        self._trips[str(trip.trip_id)] = trip


class SimpleItineraryRepo:
    def __init__(self, itinerary: Itinerary | None = None):
        self._itineraries = {str(itinerary.trip_id): itinerary} if itinerary else {}

    async def find_by_trip_id(self, trip_id: TripId):
        return self._itineraries.get(str(trip_id))

    async def save(self, itinerary: Itinerary):
        self._itineraries[str(itinerary.trip_id)] = itinerary


class SimpleBudgetRepo:
    def __init__(self, budget: TripBudget | None = None):
        self._budgets = {str(budget.trip_id): budget} if budget else {}

    async def find_by_trip_id(self, trip_id: TripId):
        return self._budgets.get(str(trip_id))

    async def save(self, budget: TripBudget):
        self._budgets[str(budget.trip_id)] = budget


class SimpleCollabRepo:
    def __init__(self, collab: TripCollaboration | None = None):
        self._collabs = {str(collab.trip_id): collab} if collab else {}

    async def find_by_trip_id(self, trip_id: TripId):
        return self._collabs.get(str(trip_id))

    async def save(self, collab: TripCollaboration):
        self._collabs[str(collab.trip_id)] = collab


class SimpleMediaRepo:
    def __init__(self, media: TripMediaCollection | None = None):
        self._media = {str(media.trip_id): media} if media else {}

    async def find_by_trip_id(self, trip_id: TripId):
        return self._media.get(str(trip_id))

    async def save(self, media: TripMediaCollection):
        self._media[str(media.trip_id)] = media


@pytest.fixture
def setup_services():
    owner_id = UserId(value=uuid.uuid4())
    editor_id = UserId(value=uuid.uuid4())
    viewer_id = UserId(value=uuid.uuid4())
    trip_id = TripId(value=uuid.uuid4())

    trip = Trip.create(
        trip_id=trip_id,
        owner_id=owner_id,
        title=TripTitle(value="Kyoto Cultural Retreat"),
        date_range=TripDateRange(departure_date=date(2026, 11, 1), return_date=date(2026, 11, 5)),
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
            user_id=editor_id,
            role=MemberRole.EDITOR,
        )
    )
    collab.members.append(
        TripMember(
            entity_id=MemberId(value=uuid.uuid4()),
            user_id=viewer_id,
            role=MemberRole.VIEWER,
        )
    )

    itinerary = Itinerary.create(
        itinerary_id=ItineraryId(value=uuid.uuid4()),
        trip_id=trip_id,
    )
    day_id = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(
        day_id=day_id,
        day_number=1,
        title="Temples & Gardens",
        date=date(2026, 11, 1),
    )

    day_id_2 = ItineraryDayId(value=uuid.uuid4())
    itinerary.add_day(
        day_id=day_id_2,
        day_number=2,
        title="Arashiyama & Bamboo Groves",
        date=date(2026, 11, 2),
    )

    budget = TripBudget.create(
        budget_id=BudgetId(value=uuid.uuid4()),
        trip_id=trip_id,
        owner_id=owner_id,
        limit=Money(amount=Decimal("2500.00"), currency="USD"),
    )
    # TripBudget.create automatically populates default categories (Food, Flights, Lodging, etc.)

    media_col = TripMediaCollection.create(
        collection_id=MediaCollectionId(value=uuid.uuid4()),
        trip_id=trip_id,
        owner_id=owner_id,
    )

    trip_repo = SimpleTripRepo(trip)
    itinerary_repo = SimpleItineraryRepo(itinerary)
    budget_repo = SimpleBudgetRepo(budget)
    collab_repo = SimpleCollabRepo(collab)
    media_repo = SimpleMediaRepo(media_col)
    action_repo = InMemoryProposedActionRepository()
    conv_repo = InMemoryAssistantConversationRepository()
    uuid_prov = StandardUUIDProvider()
    clock = SystemClock()

    itinerary_service = ItineraryService(
        repository=itinerary_repo,
        trip_repository=trip_repo,
        unit_of_work=SimpleMockUoW(),
        event_publisher=SimpleMockEventPublisher(),
        uuid_provider=uuid_prov,
    )

    budget_service = BudgetService(
        repository=budget_repo,
        trip_repository=trip_repo,
        unit_of_work=SimpleMockUoW(),
        event_publisher=SimpleMockEventPublisher(),
        uuid_provider=uuid_prov,
        clock=clock,
    )

    context_builder = AssistantContextBuilder(
        trip_repository=trip_repo,
        itinerary_repository=itinerary_repo,
        budget_repository=budget_repo,
        collaboration_repository=collab_repo,
        media_repository=media_repo,
    )

    assistant_service = AssistantService(
        assistant_engine=MockAssistantEngine(),
        context_builder=context_builder,
        action_repository=action_repo,
        conversation_repository=conv_repo,
        trip_repository=trip_repo,
        collaboration_repository=collab_repo,
        itinerary_service=itinerary_service,
        budget_service=budget_service,
        budget_repository=budget_repo,
        uuid_provider=uuid_prov,
    )

    return {
        "trip_id": trip_id,
        "owner_id": owner_id,
        "editor_id": editor_id,
        "viewer_id": viewer_id,
        "assistant_service": assistant_service,
        "action_repo": action_repo,
        "conv_repo": conv_repo,
        "itinerary_repo": itinerary_repo,
        "budget_repo": budget_repo,
        "day_id": day_id,
        "day_id_2": day_id_2,
    }


@pytest.mark.asyncio
async def test_assistant_chat_informational(setup_services):
    ctx = setup_services
    cmd = ChatCommand(
        trip_id=str(ctx["trip_id"]),
        requester_id=str(ctx["owner_id"]),
        message="What is my budget status?",
    )

    result = await ctx["assistant_service"].chat(cmd)

    assert isinstance(result, Success)
    assert result.value.response_type == AssistantResponseType.INFORMATIONAL
    assert "budget is 0.00 USD spent out of 2,500.00 USD" in result.value.message
    assert result.value.proposed_action is None


@pytest.mark.asyncio
async def test_conversation_persistence_and_multi_turn_history(setup_services):
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    # 1. Turn 1
    cmd1 = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="What is my budget status?",
    )
    res1 = await ctx["assistant_service"].chat(cmd1)
    assert isinstance(res1, Success)

    # 2. Turn 2
    cmd2 = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Can you recommend a museum on Day 1?",
    )
    res2 = await ctx["assistant_service"].chat(cmd2)
    assert isinstance(res2, Success)

    # 3. Retrieve conversation history
    query = GetHistoryQuery(trip_id=trip_id_str, requester_id=owner_id_str)
    hist_res = await ctx["assistant_service"].get_history(query)

    assert isinstance(hist_res, Success)
    history = hist_res.value
    assert len(history.messages) == 4  # 2 user messages + 2 assistant messages
    assert history.messages[0].role == "user"
    assert history.messages[0].content == "What is my budget status?"
    assert history.messages[1].role == "assistant"
    assert history.messages[2].role == "user"
    assert history.messages[2].content == "Can you recommend a museum on Day 1?"
    assert history.messages[3].role == "assistant"


@pytest.mark.asyncio
async def test_conversation_history_clear(setup_services):
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    # Chat once
    cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Hello assistant",
    )
    await ctx["assistant_service"].chat(cmd)

    # Clear history
    clear_cmd = ClearHistoryCommand(trip_id=trip_id_str, requester_id=owner_id_str)
    clear_res = await ctx["assistant_service"].clear_history(clear_cmd)
    assert isinstance(clear_res, Success)

    # Verify history is empty
    query = GetHistoryQuery(trip_id=trip_id_str, requester_id=owner_id_str)
    hist_res = await ctx["assistant_service"].get_history(query)
    assert isinstance(hist_res, Success)
    assert len(hist_res.value.messages) == 0


@pytest.mark.asyncio
async def test_assistant_chat_proposed_mutation(setup_services):
    ctx = setup_services
    cmd = ChatCommand(
        trip_id=str(ctx["trip_id"]),
        requester_id=str(ctx["owner_id"]),
        message="Please add dinner in Gion on Day 1",
    )

    result = await ctx["assistant_service"].chat(cmd)

    assert isinstance(result, Success)
    assert result.value.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.value.proposed_action is not None
    assert result.value.proposed_action.action_type in (
        AssistantActionType.PROPOSE_ADDING_ACTIVITY,
        AssistantActionType.PROPOSE_ADDING_PLACE,
    )
    assert result.value.proposed_action.status == ActionStatus.PENDING

    # Verify action stored in repository
    action = await ctx["action_repo"].find_by_id(result.value.proposed_action.action_id)
    assert action is not None


@pytest.mark.asyncio
async def test_assistant_confirm_action_owner(setup_services):
    ctx = setup_services
    # 1. Generate proposal
    chat_cmd = ChatCommand(
        trip_id=str(ctx["trip_id"]),
        requester_id=str(ctx["owner_id"]),
        message="Add a museum visit to Day 1",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Confirm action
    confirm_cmd = ConfirmActionCommand(
        trip_id=str(ctx["trip_id"]),
        action_id=action_id,
        requester_id=str(ctx["owner_id"]),
    )
    confirm_res = await ctx["assistant_service"].confirm_action(confirm_cmd)

    assert isinstance(confirm_res, Success)
    assert confirm_res.value.action.status == ActionStatus.APPLIED
    assert confirm_res.value.itinerary is not None
    assert len(confirm_res.value.itinerary.days[0].items) == 1
    assert "Museum" in confirm_res.value.itinerary.days[0].items[0].title


@pytest.mark.asyncio
async def test_budget_propose_add_expense_and_confirm(setup_services):
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    # 1. AI proposes adding an expense
    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Add expense for ramen dinner $35",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    assert isinstance(chat_res, Success)
    assert chat_res.value.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert chat_res.value.proposed_action.action_type == AssistantActionType.PROPOSE_ADDING_EXPENSE
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Owner confirms
    confirm_cmd = ConfirmActionCommand(
        trip_id=trip_id_str,
        action_id=action_id,
        requester_id=owner_id_str,
    )
    confirm_res = await ctx["assistant_service"].confirm_action(confirm_cmd)

    assert isinstance(confirm_res, Success)
    assert confirm_res.value.action.status == ActionStatus.APPLIED
    assert confirm_res.value.expense is not None
    assert confirm_res.value.expense.amount == Decimal("35.00")

    # Verify in budget repo
    budget = await ctx["budget_repo"].find_by_trip_id(ctx["trip_id"])
    assert len(budget.expenses) == 1
    assert budget.total_spent.amount == Decimal("35.00")


@pytest.mark.asyncio
async def test_budget_propose_update_limit_and_confirm(setup_services):
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    editor_id_str = str(ctx["editor_id"])

    # 1. AI proposes updating budget limit
    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=editor_id_str,
        message="Increase budget limit to $3000",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    assert isinstance(chat_res, Success)
    assert chat_res.value.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert chat_res.value.proposed_action.action_type == AssistantActionType.PROPOSE_UPDATING_BUDGET_LIMIT
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Editor confirms
    confirm_cmd = ConfirmActionCommand(
        trip_id=trip_id_str,
        action_id=action_id,
        requester_id=editor_id_str,
    )
    confirm_res = await ctx["assistant_service"].confirm_action(confirm_cmd)

    assert isinstance(confirm_res, Success)
    assert confirm_res.value.action.status == ActionStatus.APPLIED
    assert confirm_res.value.budget is not None
    assert confirm_res.value.budget.limit == Decimal("3000.00")

    # Verify in budget repo
    budget = await ctx["budget_repo"].find_by_trip_id(ctx["trip_id"])
    assert budget.limit.amount == Decimal("3000.00")


@pytest.mark.asyncio
async def test_budget_confirm_forbidden_for_viewer(setup_services):
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    viewer_id_str = str(ctx["viewer_id"])

    # 1. Propose expense
    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=viewer_id_str,
        message="Add expense for taxi $20",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Viewer attempts to confirm
    confirm_cmd = ConfirmActionCommand(
        trip_id=trip_id_str,
        action_id=action_id,
        requester_id=viewer_id_str,
    )
    confirm_res = await ctx["assistant_service"].confirm_action(confirm_cmd)

    assert isinstance(confirm_res, Failure)
    assert isinstance(confirm_res.error, ForbiddenError)


@pytest.mark.asyncio
async def test_assistant_reject_action(setup_services):
    ctx = setup_services
    # 1. Generate proposal
    chat_cmd = ChatCommand(
        trip_id=str(ctx["trip_id"]),
        requester_id=str(ctx["owner_id"]),
        message="Add dinner on Day 1",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Reject action
    reject_cmd = RejectActionCommand(
        trip_id=str(ctx["trip_id"]),
        action_id=action_id,
        requester_id=str(ctx["owner_id"]),
    )
    reject_res = await ctx["assistant_service"].reject_action(reject_cmd)

    assert isinstance(reject_res, Success)
    assert reject_res.value.action.status == ActionStatus.REJECTED

    # Itinerary remains unchanged (no items added)
    itinerary = await ctx["itinerary_repo"].find_by_trip_id(ctx["trip_id"])
    assert len(itinerary.days[0].items) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 11: Grounded Places & Travel Intelligence Tests
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_assistant_grounded_place_search_and_proposal(setup_services):
    """Test searching for a restaurant returns grounded Place provider details."""
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Find a good vegetarian restaurant near Day 2",
    )
    result = await ctx["assistant_service"].chat(chat_cmd)

    assert isinstance(result, Success)
    assert result.value.response_type == AssistantResponseType.PROPOSED_MUTATION
    assert result.value.proposed_action is not None
    assert result.value.proposed_action.action_type == AssistantActionType.PROPOSE_ADDING_PLACE

    payload = result.value.proposed_action.payload
    assert payload.get("provider_place_id") is not None
    assert payload.get("place_name") is not None
    assert payload.get("formatted_address") is not None
    assert payload.get("rating") is not None
    assert payload.get("is_verified") is True
    assert payload.get("day_number") == 2
    assert AssistantActionType.SEARCH_PLACES in result.value.tools_used


@pytest.mark.asyncio
async def test_assistant_unverified_place_rejection(setup_services):
    """Test unverified / fictional place queries return safe message without hallucinating."""
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Find a place called Atlantis Underwater Dining",
    )
    result = await ctx["assistant_service"].chat(chat_cmd)

    assert isinstance(result, Success)
    assert result.value.response_type == AssistantResponseType.INFORMATIONAL
    assert result.value.proposed_action is None
    assert "no verified" in result.value.message.lower() or "not found" in result.value.message.lower()


@pytest.mark.asyncio
async def test_confirm_grounded_place_adds_to_itinerary(setup_services):
    """Test confirming a grounded place adds it to the target day in ItineraryService."""
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    # 1. Generate grounded place proposal for Day 2
    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Find a restaurant near Day 2",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Owner confirms proposal
    confirm_cmd = ConfirmActionCommand(
        trip_id=trip_id_str,
        action_id=action_id,
        requester_id=owner_id_str,
    )
    confirm_res = await ctx["assistant_service"].confirm_action(confirm_cmd)

    assert isinstance(confirm_res, Success)
    assert confirm_res.value.action.status == ActionStatus.APPLIED
    assert confirm_res.value.itinerary is not None

    # Check Day 2 has the new item
    day_2 = next((d for d in confirm_res.value.itinerary.days if d.day_number == 2), None)
    assert day_2 is not None
    assert len(day_2.items) == 1
    assert "Trattoria Da Enzo" in day_2.items[0].title or "restaurant" in day_2.items[0].item_type.lower()


@pytest.mark.asyncio
async def test_viewer_cannot_confirm_grounded_place(setup_services):
    """Test viewer confirmation on grounded place is blocked with 403 Forbidden."""
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    viewer_id_str = str(ctx["viewer_id"])

    # 1. Viewer requests place search
    chat_cmd = ChatCommand(
        trip_id=trip_id_str,
        requester_id=viewer_id_str,
        message="Find a cafe near Day 1",
    )
    chat_res = await ctx["assistant_service"].chat(chat_cmd)
    action_id = str(chat_res.value.proposed_action.action_id)

    # 2. Viewer attempts to confirm
    confirm_cmd = ConfirmActionCommand(
        trip_id=trip_id_str,
        action_id=action_id,
        requester_id=viewer_id_str,
    )
    confirm_res = await ctx["assistant_service"].confirm_action(confirm_cmd)

    assert isinstance(confirm_res, Failure)
    assert isinstance(confirm_res.error, ForbiddenError)


@pytest.mark.asyncio
async def test_duplicate_place_on_same_day_rejected(setup_services):
    """Test adding the same venue or title to the same day twice returns a validation error."""
    ctx = setup_services
    trip_id_str = str(ctx["trip_id"])
    owner_id_str = str(ctx["owner_id"])

    # 1. Propose & confirm place for Day 1
    chat_cmd1 = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Find restaurant near Day 1",
    )
    chat_res1 = await ctx["assistant_service"].chat(chat_cmd1)
    action_id1 = str(chat_res1.value.proposed_action.action_id)

    confirm_res1 = await ctx["assistant_service"].confirm_action(
        ConfirmActionCommand(
            trip_id=trip_id_str,
            action_id=action_id1,
            requester_id=owner_id_str,
        )
    )
    assert isinstance(confirm_res1, Success)

    # 2. Propose the same place again for Day 1
    chat_cmd2 = ChatCommand(
        trip_id=trip_id_str,
        requester_id=owner_id_str,
        message="Find restaurant near Day 1",
    )
    chat_res2 = await ctx["assistant_service"].chat(chat_cmd2)
    action_id2 = str(chat_res2.value.proposed_action.action_id)

    # 3. Attempting to confirm duplicate fails
    confirm_res2 = await ctx["assistant_service"].confirm_action(
        ConfirmActionCommand(
            trip_id=trip_id_str,
            action_id=action_id2,
            requester_id=owner_id_str,
        )
    )
    assert isinstance(confirm_res2, Failure)
    assert "already scheduled" in str(confirm_res2.error.message)


