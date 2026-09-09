"""AssistantService — Orchestration service for trip-scoped AI interactions, persistent multi-turn memory, and safe action execution."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
import logging
from typing import Any
from uuid import UUID

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.assistant.application.commands import (
    ChatCommand,
    ClearHistoryCommand,
    ConfirmActionCommand,
    GetHistoryQuery,
    RejectActionCommand,
)
from app.modules.travel.assistant.application.dtos import (
    ChatResponseDTO,
    ConfirmActionResultDTO,
    ConversationHistoryDTO,
    PersistedMessageDTO,
    ProposedActionDTO,
    RejectActionResultDTO,
    TripWarningsDTO,
)
from app.modules.travel.assistant.application.services.assistant_context_builder import (
    AssistantContextBuilder,
)
from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
    ProactiveIntelligenceService,
)
from app.modules.travel.assistant.domain.entities.conversation import (
    AssistantConversation,
)
from app.modules.travel.assistant.domain.entities.proposed_action import ProposedAction
from app.modules.travel.assistant.domain.enums import (
    ActionStatus,
    AssistantActionType,
    AssistantResponseType,
)
from app.modules.travel.assistant.domain.errors import (
    ActionAlreadyExecutedError,
    ActionPermissionError,
    ActionValidationError,
    ProposedActionNotFoundError,
)
from app.modules.travel.assistant.domain.repositories.conversation_repository import (
    IAssistantConversationRepository,
)
from app.modules.travel.assistant.domain.repositories.interfaces import (
    IProposedActionRepository,
)
from app.modules.travel.assistant.domain.value_objects import (
    ActionId,
    ChatMessage,
    ConversationId,
    MessageId,
)
from app.modules.travel.assistant.infrastructure.engine.base import AssistantEngine
from app.modules.travel.budget.application.budget_service import BudgetService
from app.modules.travel.budget.application.commands import (
    AddExpenseCommand,
    UpdateBudgetCommand,
)
from app.modules.travel.budget.domain.repositories.interfaces import (
    ITripBudgetRepository,
)
from app.modules.travel.itinerary.application.commands import (
    AddItineraryDayCommand,
    AddItineraryItemCommand,
    RemoveItineraryItemCommand,
    UpdateItineraryDayCommand,
    UpdateItineraryItemCommand,
)
from app.modules.travel.itinerary.application.dtos import ItinerarySummary
from app.modules.travel.itinerary.application.itinerary_service import ItineraryService
from app.modules.travel.itinerary.application.queries import GetItineraryQuery
from app.modules.travel.sharing.domain.enums.member_role import MemberRole
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.trips.domain.errors import TripNotFoundError
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.services.maps.factory import get_routing_provider
from app.shared.domain.errors import ForbiddenError, TravixError, ValidationError
from app.shared.domain.result import Failure, Result, Success
from app.shared.domain.uuid_provider import UUIDProvider


logger = logging.getLogger(__name__)


class AssistantService:
    """Application service coordinating AI conversations, multi-turn memory, and safe mutations."""

    def __init__(
        self,
        assistant_engine: AssistantEngine,
        context_builder: AssistantContextBuilder,
        action_repository: IProposedActionRepository,
        conversation_repository: IAssistantConversationRepository,
        trip_repository: ITripRepository,
        collaboration_repository: ITripCollaborationRepository,
        itinerary_service: ItineraryService,
        budget_service: BudgetService,
        budget_repository: ITripBudgetRepository,
        uuid_provider: UUIDProvider,
        proactive_intelligence_service: ProactiveIntelligenceService | None = None,
    ) -> None:
        self._engine = assistant_engine
        self._context_builder = context_builder
        self._action_repo = action_repository
        self._conversation_repo = conversation_repository
        self._trip_repo = trip_repository
        self._collab_repo = collaboration_repository
        self._itinerary_service = itinerary_service
        self._budget_service = budget_service
        self._budget_repo = budget_repository
        self._uuid_provider = uuid_provider
        self._proactive_service = (
            proactive_intelligence_service
            or ProactiveIntelligenceService(
                itinerary_repository=itinerary_service._repository,
                budget_repository=budget_repository,
                routing_provider=get_routing_provider(),
            )
        )


    async def chat(self, command: ChatCommand) -> Result[ChatResponseDTO, TravixError]:
        """Process a conversational turn, maintain persistent history, and return structured response."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))

        # Verify access (owner or member)
        if not await self._has_trip_access(trip_id, trip.owner_id, requester_id):
            return Failure(ForbiddenError("You do not have access to this trip."))

        # 1. Load or create persistent conversation
        conversation = await self._conversation_repo.find_by_trip_and_user(
            trip_id, requester_id
        )
        if conversation is None:
            conv_id = ConversationId(value=self._uuid_provider.generate())
            conversation = AssistantConversation.create(
                conversation_id=conv_id,
                trip_id=trip_id,
                user_id=requester_id,
            )

        # 2. Append User Message
        user_msg_id = MessageId(value=self._uuid_provider.generate())
        conversation.add_user_message(
            message_id=user_msg_id,
            content=command.message,
        )

        # 3. Build bounded history from conversation (last 8 messages)
        bounded_history_messages = conversation.get_bounded_history(limit=8)
        history_objs = [
            ChatMessage(
                role=m.role,
                content=m.content,
                timestamp=m.created_at,
            )
            for m in bounded_history_messages[:-1]  # exclude the user message just added
        ]

        # 4. Build real-time trip context
        context = await self._context_builder.build_context(trip, requester_id)

        # 5. Call AI Engine
        try:
            engine_result = await self._engine.chat(
                context=context,
                user_message=command.message,
                history=history_objs,
            )
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            logger.error("AI engine execution failed: %s", exc, exc_info=True)
            return Failure(TravixError(f"AI Assistant error: {exc}"))

        # 6. Save ProposedAction if generated
        proposed_action_dto: ProposedActionDTO | None = None
        action_id_for_msg: ActionId | None = None

        if (
            engine_result.response_type == AssistantResponseType.PROPOSED_MUTATION
            and engine_result.proposed_action is not None
        ):
            pa_data = engine_result.proposed_action
            action_id = ActionId(value=self._uuid_provider.generate())
            action_id_for_msg = action_id
            action = ProposedAction.create(
                action_id=action_id,
                trip_id=trip_id,
                action_type=pa_data.action_type,
                summary=pa_data.summary,
                description=pa_data.description,
                payload=pa_data.payload,
            )
            await self._action_repo.save(action)
            proposed_action_dto = self._to_action_dto(action)

        # 7. Append Assistant Message to conversation and persist
        assistant_msg_id = MessageId(value=self._uuid_provider.generate())
        conversation.add_assistant_message(
            message_id=assistant_msg_id,
            content=engine_result.message,
            response_type=engine_result.response_type,
            action_id=action_id_for_msg,
            tools_used=engine_result.tools_used,
        )
        await self._conversation_repo.save(conversation)

        response_dto = ChatResponseDTO(
            message=engine_result.message,
            response_type=engine_result.response_type,
            proposed_action=proposed_action_dto,
            tools_used=engine_result.tools_used,
        )
        return Success(response_dto)

    async def get_history(
        self, query: GetHistoryQuery
    ) -> Result[ConversationHistoryDTO, TravixError]:
        """Retrieve persisted conversation history for a trip and user."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))

        if not await self._has_trip_access(trip_id, trip.owner_id, requester_id):
            return Failure(ForbiddenError("You do not have access to this trip."))

        conversation = await self._conversation_repo.find_by_trip_and_user(
            trip_id, requester_id
        )
        if conversation is None:
            conv_id = ConversationId(value=self._uuid_provider.generate())
            conversation = AssistantConversation.create(
                conversation_id=conv_id,
                trip_id=trip_id,
                user_id=requester_id,
            )
            await self._conversation_repo.save(conversation)

        persisted_msgs = [
            PersistedMessageDTO(
                message_id=m.entity_id.value,
                role=m.role,
                content=m.content,
                response_type=m.response_type,
                action_id=m.action_id.value if m.action_id else None,
                tools_used=m.tools_used,
                created_at=m.created_at,
            )
            for m in conversation.messages
        ]

        return Success(
            ConversationHistoryDTO(
                conversation_id=conversation.entity_id.value,
                trip_id=conversation.trip_id.value,
                user_id=conversation.user_id.value,
                messages=tuple(persisted_msgs),
            )
        )

    async def clear_history(
        self, command: ClearHistoryCommand
    ) -> Result[bool, TravixError]:
        """Clear the conversation history for a trip and user."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))

        conversation = await self._conversation_repo.find_by_trip_and_user(
            trip_id, requester_id
        )
        if conversation:
            conversation.clear_messages()
            await self._conversation_repo.save(conversation)

        return Success(True)

    async def confirm_action(
        self, command: ConfirmActionCommand
    ) -> Result[ConfirmActionResultDTO, TravixError]:
        """Validate and execute a proposed action via existing domain services."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            action_id = ActionId.from_str(command.action_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))

        # Permissions check: Viewers must NEVER execute mutations!
        role = await self._get_user_role(trip_id, trip.owner_id, requester_id)
        if role == "viewer" or role is None:
            return Failure(
                ForbiddenError("Viewers are not permitted to modify trip details.")
            )

        action = await self._action_repo.find_by_id(action_id)
        if action is None or action.trip_id != trip_id:
            return Failure(ProposedActionNotFoundError(str(action_id)))

        if action.status != ActionStatus.PENDING:
            return Failure(ActionAlreadyExecutedError(str(action_id), action.status.value))

        itinerary_summary = None
        expense_summary = None
        budget_summary = None
        payload = action.payload

        # 1. Itinerary Actions
        if action.action_type in (
            AssistantActionType.PROPOSE_ADDING_ACTIVITY,
            AssistantActionType.PROPOSE_ADDING_PLACE,
        ):
            day_id = payload.get("day_id")
            if not day_id:
                day_cmd = AddItineraryDayCommand(
                    trip_id=str(trip_id),
                    requester_id=str(trip.owner_id),
                    day_number=payload.get("day_number", 1),
                    title=f"Day {payload.get('day_number', 1)}",
                )
                day_res = await self._itinerary_service.add_day(day_cmd)
                if isinstance(day_res, Failure):
                    return Failure(day_res.error)
                for d in day_res.value.days:
                    if d.day_number == payload.get("day_number", 1):
                        day_id = str(d.day_id)
                        break

            # Prevent duplicate item/venue on the same day
            target_title = (payload.get("title") or payload.get("place_name") or "").strip().lower()
            if day_id and target_title:
                itin = await self._itinerary_service._repository.find_by_trip_id(trip_id)
                if itin:
                    for d in itin.days:
                        if str(d.entity_id) == str(day_id):
                            for existing_item in d.items:
                                if existing_item.title.value.strip().lower() == target_title:
                                    return Failure(
                                        ActionValidationError(
                                            f"'{existing_item.title.value}' is already scheduled on this day."
                                        )
                                    )

            start_time_val = None
            if payload.get("start_time"):
                try:
                    start_time_val = time.fromisoformat(payload["start_time"])
                except Exception:
                    pass

            end_time_val = None
            if payload.get("end_time"):
                try:
                    end_time_val = time.fromisoformat(payload["end_time"])
                except Exception:
                    pass

            cost_val = None
            if payload.get("cost"):
                try:
                    cost_val = Decimal(str(payload["cost"]))
                except Exception:
                    pass

            item_title = payload.get("place_name") or payload.get("title") or "New Activity"
            item_desc = payload.get("description")
            if not item_desc and payload.get("formatted_address"):
                item_desc = f"Verified place: {payload.get('formatted_address')}"

            item_cmd = AddItineraryItemCommand(
                trip_id=str(trip_id),
                day_id=str(day_id),
                requester_id=str(trip.owner_id),
                title=item_title,
                item_type=payload.get("item_type", "activity"),
                description=item_desc,
                start_time=start_time_val,
                end_time=end_time_val,
                cost=cost_val,
                currency=payload.get("currency", "USD"),
            )
            item_res = await self._itinerary_service.add_item(item_cmd)
            if isinstance(item_res, Failure):
                return Failure(item_res.error)
            itinerary_summary = item_res.value


        elif action.action_type == AssistantActionType.PROPOSE_REMOVING_ACTIVITY:
            item_id = payload.get("item_id")
            valid_uuid = False
            if item_id:
                try:
                    uuid.UUID(str(item_id))
                    valid_uuid = True
                except Exception:
                    valid_uuid = False

            if not valid_uuid:
                itin = await self._get_itinerary_summary_safe(trip_id, trip.owner_id)
                if itin:
                    for d in itin.days:
                        if d.items:
                            for it in d.items:
                                if payload.get("item_title") and payload["item_title"].lower() in it.title.lower():
                                    item_id = str(it.item_id)
                                    break
                            if not item_id:
                                item_id = str(d.items[-1].item_id)
                            break

            if not item_id:
                return Failure(ActionValidationError("Item ID is missing from action payload."))

            rem_cmd = RemoveItineraryItemCommand(
                trip_id=str(trip_id),
                item_id=str(item_id),
                requester_id=str(trip.owner_id),
            )
            rem_res = await self._itinerary_service.remove_item(rem_cmd)
            if isinstance(rem_res, Failure):
                return Failure(rem_res.error)
            itinerary_summary = rem_res.value

        elif action.action_type == AssistantActionType.PROPOSE_ITINERARY_CHANGE:
            day_id = payload.get("day_id")
            if not day_id:
                itin = await self._get_itinerary_summary_safe(trip_id, trip.owner_id)
                if itin and itin.days:
                    day_id = str(itin.days[0].day_id)
            if day_id and payload.get("title"):
                upd_cmd = UpdateItineraryDayCommand(
                    trip_id=str(trip_id),
                    day_id=str(day_id),
                    requester_id=str(trip.owner_id),
                    day_number=payload.get("day_number", 1),
                    title=payload.get("title"),
                )
                upd_res = await self._itinerary_service.update_day(upd_cmd)
                if isinstance(upd_res, Failure):
                    return Failure(upd_res.error)
                itinerary_summary = upd_res.value

        elif action.action_type == AssistantActionType.PROPOSE_RESCHEDULING_ACTIVITY:
            item_id = payload.get("item_id")
            day_id = payload.get("day_id")

            valid_uuid = False
            if item_id:
                try:
                    uuid.UUID(str(item_id))
                    valid_uuid = True
                except Exception:
                    valid_uuid = False

            if not valid_uuid or not day_id:
                itin = await self._get_itinerary_summary_safe(trip_id, trip.owner_id)
                if itin:
                    for d in itin.days:
                        # Match by day_id or day_number if available
                        day_match = True
                        if day_id and str(d.day_id) != str(day_id):
                            day_match = False
                        if day_match and d.items:
                            # Try word-level matching first
                            matched = False
                            for it in d.items:
                                search_term = payload.get("title", "").lower()
                                if any(w in it.title.lower() for w in ["lunch", "food", "dining", "meal", "restaurant", "cafe"]) if "lunch" in search_term else (search_term and search_term in it.title.lower()):
                                    item_id = str(it.item_id)
                                    day_id = str(d.day_id)
                                    matched = True
                                    break
                            if not matched and d.items:
                                item_id = str(d.items[0].item_id)
                                day_id = str(d.day_id)
                            break

            if not item_id or item_id == "None":
                return Failure(ActionValidationError("Cannot reschedule activity: No itinerary item found."))

            start_time_val = None
            if payload.get("start_time"):
                try:
                    start_time_val = time.fromisoformat(payload["start_time"])
                except Exception:
                    pass

            end_time_val = None
            if payload.get("end_time"):
                try:
                    end_time_val = time.fromisoformat(payload["end_time"])
                except Exception:
                    pass

            cost_val = None
            if payload.get("cost"):
                try:
                    cost_val = Decimal(str(payload["cost"]))
                except Exception:
                    pass

            upd_item_cmd = UpdateItineraryItemCommand(
                trip_id=str(trip_id),
                item_id=str(item_id),
                day_id=str(day_id) if day_id else None,
                requester_id=str(trip.owner_id),
                title=payload.get("title", ""),
                item_type=payload.get("item_type", "activity"),
                description=payload.get("description"),
                start_time=start_time_val,
                end_time=end_time_val,
                cost=cost_val,
                currency=payload.get("currency", "USD"),
            )
            upd_item_res = await self._itinerary_service.update_item(upd_item_cmd)
            if isinstance(upd_item_res, Failure):
                return Failure(upd_item_res.error)
            itinerary_summary = upd_item_res.value

        elif action.action_type == AssistantActionType.PROPOSE_REPLACING_ACTIVITY:
            old_item_id = payload.get("old_item_id") or payload.get("item_id")
            day_id = payload.get("day_id")

            # 1. Remove old item if present
            valid_old_uuid = False
            if old_item_id:
                try:
                    uuid.UUID(str(old_item_id))
                    valid_old_uuid = True
                except Exception:
                    valid_old_uuid = False

            if not valid_old_uuid or not day_id:
                itin = await self._get_itinerary_summary_safe(trip_id, trip.owner_id)
                if itin:
                    for d in itin.days:
                        for it in d.items:
                            if payload.get("old_title") and payload["old_title"].lower() in it.title.lower():
                                old_item_id = str(it.item_id)
                                day_id = str(d.day_id)
                                break
                        if old_item_id:
                            break

            if old_item_id:
                rem_cmd = RemoveItineraryItemCommand(
                    trip_id=str(trip_id),
                    item_id=str(old_item_id),
                    requester_id=str(trip.owner_id),
                )
                rem_res = await self._itinerary_service.remove_item(rem_cmd)
                if isinstance(rem_res, Failure):
                    logger.warning("Replacing activity: old item remove returned %s, continuing", rem_res.error)

            # 2. Add replacement item
            if not day_id:
                itin = await self._get_itinerary_summary_safe(trip_id, trip.owner_id)
                if itin and itin.days:
                    day_id = str(itin.days[0].day_id)

            start_time_val = None
            if payload.get("start_time"):
                try:
                    start_time_val = time.fromisoformat(payload["start_time"])
                except Exception:
                    pass

            end_time_val = None
            if payload.get("end_time"):
                try:
                    end_time_val = time.fromisoformat(payload["end_time"])
                except Exception:
                    pass

            cost_val = None
            if payload.get("cost"):
                try:
                    cost_val = Decimal(str(payload["cost"]))
                except Exception:
                    pass

            item_title = payload.get("title") or payload.get("place_name") or "Replacement Activity"
            item_desc = payload.get("description") or f"Verified replacement venue: {item_title}"

            add_cmd = AddItineraryItemCommand(
                trip_id=str(trip_id),
                day_id=str(day_id),
                requester_id=str(trip.owner_id),
                title=item_title,
                item_type=payload.get("item_type", "sightseeing"),
                description=item_desc,
                start_time=start_time_val,
                end_time=end_time_val,
                cost=cost_val,
                currency=payload.get("currency", "USD"),
            )
            add_res = await self._itinerary_service.add_item(add_cmd)
            if isinstance(add_res, Failure):
                return Failure(add_res.error)
            itinerary_summary = add_res.value

        elif action.action_type == AssistantActionType.PROPOSE_REORDERING_ACTIVITIES:
            day_id = payload.get("day_id")
            if day_id and payload.get("title"):
                upd_cmd = UpdateItineraryDayCommand(
                    trip_id=str(trip_id),
                    day_id=str(day_id),
                    requester_id=str(trip.owner_id),
                    day_number=payload.get("day_number"),
                    title=payload.get("title"),
                )
                upd_res = await self._itinerary_service.update_day(upd_cmd)
                if isinstance(upd_res, Failure):
                    return Failure(upd_res.error)
                itinerary_summary = upd_res.value

        # 2. Budget Actions
        elif action.action_type == AssistantActionType.PROPOSE_ADDING_EXPENSE:
            cat_id = payload.get("category_id")
            # If no category_id in payload, resolve from existing budget categories
            if not cat_id:
                budget = await self._budget_repo.find_by_trip_id(trip_id)
                if budget and budget.categories:
                    cat_id = str(budget.categories[0].entity_id)
                else:
                    return Failure(ActionValidationError("Cannot log expense: No budget categories available."))

            exp_date = date.today()
            if payload.get("expense_date"):
                try:
                    exp_date = date.fromisoformat(payload["expense_date"])
                except Exception:
                    pass

            raw_type = payload.get("expense_type", "other")
            if raw_type not in ["activity", "transport", "lodging", "restaurant", "other"]:
                raw_type = "other"

            exp_cmd = AddExpenseCommand(
                trip_id=str(trip_id),
                title=payload.get("title", "Expense"),
                amount=Decimal(str(payload.get("amount", "0.00"))),
                category_id=str(cat_id),
                expense_type=raw_type,
                expense_date=exp_date,
                description=payload.get("description"),
                requester_id=str(trip.owner_id),
            )
            exp_res = await self._budget_service.add_expense(exp_cmd)
            if isinstance(exp_res, Failure):
                return Failure(exp_res.error)
            expense_summary = exp_res.value

        elif action.action_type in (
            AssistantActionType.PROPOSE_UPDATING_BUDGET_LIMIT,
            AssistantActionType.PROPOSE_ADJUSTING_BUDGET,
        ):
            raw_limit = payload.get("limit_amount") or payload.get("new_limit") or "0.00"
            limit_amount = Decimal(str(raw_limit))
            upd_b_cmd = UpdateBudgetCommand(
                trip_id=str(trip_id),
                limit_amount=limit_amount,
                status=None,
                requester_id=str(trip.owner_id),
            )
            upd_b_res = await self._budget_service.update_budget(upd_b_cmd)
            if isinstance(upd_b_res, Failure):
                return Failure(upd_b_res.error)
            budget_summary = upd_b_res.value


        action.mark_applied()
        await self._action_repo.save(action)

        return Success(
            ConfirmActionResultDTO(
                action=self._to_action_dto(action),
                itinerary=itinerary_summary,
                expense=expense_summary,
                budget=budget_summary,
                message="Proposed mutation successfully executed and applied.",
            )
        )

    async def reject_action(
        self, command: RejectActionCommand
    ) -> Result[RejectActionResultDTO, TravixError]:
        """Cancel/reject a proposed action without modifying any trip data."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            action_id = ActionId.from_str(command.action_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_id)))

        if not await self._has_trip_access(trip_id, trip.owner_id, requester_id):
            return Failure(ForbiddenError("You do not have access to this trip."))

        action = await self._action_repo.find_by_id(action_id)
        if action is None or action.trip_id != trip_id:
            return Failure(ProposedActionNotFoundError(str(action_id)))

        if action.status != ActionStatus.PENDING:
            return Failure(ActionAlreadyExecutedError(str(action_id), action.status.value))

        action.mark_rejected()
        await self._action_repo.save(action)

        return Success(
            RejectActionResultDTO(
                action=self._to_action_dto(action),
                message="Proposed action cancelled.",
            )
        )

    async def get_warnings(
        self, trip_id: str, requester_id: str
    ) -> Result[TripWarningsDTO, TravixError]:
        """Retrieve proactive travel warnings (itinerary conflicts, travel feasibility, budget risks). Accessible to Owners, Editors, and Viewers."""
        try:
            trip_uuid = TripId.from_str(trip_id)
            user_uuid = UserId.from_str(requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        trip = await self._trip_repo.find_by_id(trip_uuid)
        if trip is None or trip.is_deleted:
            return Failure(TripNotFoundError(str(trip_uuid)))

        if not await self._has_trip_access(trip_uuid, trip.owner_id, user_uuid):
            return Failure(ForbiddenError("You do not have access to this trip."))

        warnings_dto = await self._proactive_service.get_trip_warnings_dto(trip_uuid)
        return Success(warnings_dto)

    async def _has_trip_access(
        self, trip_id: TripId, owner_id: UserId, requester_id: UserId
    ) -> bool:
        if owner_id == requester_id:
            return True
        collab = await self._collab_repo.find_by_trip_id(trip_id)
        if collab:
            return any(m.user_id == requester_id for m in collab.members)
        return False

    async def _get_user_role(
        self, trip_id: TripId, owner_id: UserId, requester_id: UserId
    ) -> str | None:
        if owner_id == requester_id:
            return "owner"
        collab = await self._collab_repo.find_by_trip_id(trip_id)
        if collab:
            for m in collab.members:
                if m.user_id == requester_id:
                    return m.role.value
        return None

    async def _get_itinerary_summary_safe(
        self, trip_id: TripId, owner_id: UserId
    ) -> ItinerarySummary | None:
        """Fetch full itinerary summary with days and items safely."""
        try:
            q = GetItineraryQuery(trip_id=str(trip_id), requester_id=str(owner_id))
            res = await self._itinerary_service.get_itinerary(q)
            if isinstance(res, Success):
                return res.value
        except Exception as exc:
            logger.warning("Failed to fetch itinerary summary: %s", exc)
        return None

    def _to_action_dto(self, action: ProposedAction) -> ProposedActionDTO:
        action_id = action.entity_id.value if hasattr(action.entity_id, "value") else action.entity_id
        trip_id = action.trip_id.value if hasattr(action.trip_id, "value") else action.trip_id
        return ProposedActionDTO(
            action_id=action_id,
            trip_id=trip_id,
            action_type=action.action_type,
            summary=action.summary,
            description=action.description,
            payload=action.payload,
            status=action.status,
            created_at=action.created_at,
            applied_at=action.applied_at,
        )
