"""Assistant Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.assistant.application.commands import (
    ChatCommand,
    ClearHistoryCommand,
    ConfirmActionCommand,
    GetHistoryQuery,
    RejectActionCommand,
)
from app.modules.travel.assistant.domain.value_objects import ChatMessage
from app.modules.travel.assistant.infrastructure.dependencies import (
    CurrentAssistantService,
)
from app.modules.travel.assistant.presentation.error_responses import (
    map_assistant_failure,
)
from app.modules.travel.assistant.presentation.schemas import (
    ChatAssistantRequest,
    ChatAssistantResponse,
    ConfirmActionResponse,
    ConversationHistoryResponse,
    DataEnvelope,
    PersistedMessageSchema,
    ProposedActionSchema,
    RejectActionResponse,
    TravelWarningSchema,
    TripWarningsResponse,
)
from app.modules.travel.budget.presentation.schemas import (
    BudgetResponse,
    ExpenseResponse,
)
from app.modules.travel.itinerary.presentation.schemas import ItineraryResponse
from app.shared.domain.result import Failure, Success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trips", tags=["AI Assistant"])


@router.post(
    "/{trip_id}/assistant/chat",
    response_model=DataEnvelope[ChatAssistantResponse],
    status_code=status.HTTP_200_OK,
    summary="Chat with Trip AI Assistant",
    description="Send a message to the trip-scoped AI assistant with persistent multi-turn history. Returns conversational replies and structured proposed actions.",
)
async def chat_with_assistant(
    trip_id: str,
    body: ChatAssistantRequest,
    current_user: RequireAuthentication,
    assistant_service: CurrentAssistantService,
) -> DataEnvelope[ChatAssistantResponse] | JSONResponse:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/assistant/chat"

    history_objs = [
        ChatMessage(role=h.role, content=h.content, timestamp=h.timestamp)
        for h in body.history
    ] if body.history else []

    command = ChatCommand(
        trip_id=trip_id,
        requester_id=str(current_user.user_id),
        message=body.message,
        history=history_objs,
    )

    result = await assistant_service.chat(command)

    if isinstance(result, Failure):
        return map_assistant_failure(
            result.error, trace_id=trace_id, instance=instance
        )

    dto = result.value
    pa_schema = None
    if dto.proposed_action:
        pa_schema = ProposedActionSchema(
            action_id=dto.proposed_action.action_id,
            trip_id=dto.proposed_action.trip_id,
            action_type=dto.proposed_action.action_type,
            summary=dto.proposed_action.summary,
            description=dto.proposed_action.description,
            payload=dto.proposed_action.payload,
            status=dto.proposed_action.status,
            created_at=dto.proposed_action.created_at,
            applied_at=dto.proposed_action.applied_at,
        )

    response_data = ChatAssistantResponse(
        message=dto.message,
        response_type=dto.response_type,
        proposed_action=pa_schema,
        tools_used=list(dto.tools_used),
    )

    return DataEnvelope(data=response_data)


@router.get(
    "/{trip_id}/assistant/history",
    response_model=DataEnvelope[ConversationHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Assistant Conversation History",
    description="Retrieve persisted multi-turn chat history for the authenticated user and trip.",
)
async def get_conversation_history(
    trip_id: str,
    current_user: RequireAuthentication,
    assistant_service: CurrentAssistantService,
) -> DataEnvelope[ConversationHistoryResponse] | JSONResponse:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/assistant/history"

    query = GetHistoryQuery(
        trip_id=trip_id,
        requester_id=str(current_user.user_id),
    )

    result = await assistant_service.get_history(query)

    if isinstance(result, Failure):
        return map_assistant_failure(
            result.error, trace_id=trace_id, instance=instance
        )

    dto = result.value
    messages_schema = [
        PersistedMessageSchema(
            message_id=m.message_id,
            role=m.role,
            content=m.content,
            response_type=m.response_type,
            action_id=m.action_id,
            tools_used=list(m.tools_used),
            created_at=m.created_at,
        )
        for m in dto.messages
    ]

    history_data = ConversationHistoryResponse(
        conversation_id=dto.conversation_id,
        trip_id=dto.trip_id,
        user_id=dto.user_id,
        messages=messages_schema,
    )

    return DataEnvelope(data=history_data)


@router.delete(
    "/{trip_id}/assistant/history",
    status_code=status.HTTP_200_OK,
    summary="Clear Assistant Conversation History",
    description="Clear the persisted conversation history for this trip and user.",
)
async def clear_conversation_history(
    trip_id: str,
    current_user: RequireAuthentication,
    assistant_service: CurrentAssistantService,
) -> JSONResponse:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/assistant/history"

    command = ClearHistoryCommand(
        trip_id=trip_id,
        requester_id=str(current_user.user_id),
    )

    result = await assistant_service.clear_history(command)

    if isinstance(result, Failure):
        return map_assistant_failure(
            result.error, trace_id=trace_id, instance=instance
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"data": {"cleared": True, "message": "Conversation history cleared."}},
    )


@router.post(
    "/{trip_id}/assistant/actions/{action_id}/confirm",
    response_model=DataEnvelope[ConfirmActionResponse],
    status_code=status.HTTP_200_OK,
    summary="Confirm and Execute Proposed Action",
    description="Confirms a pending AI-proposed mutation (itinerary change or budget mutation) and applies it using existing domain CQRS services. Restricted to Owners and Editors.",
)
async def confirm_action(
    trip_id: str,
    action_id: str,
    current_user: RequireAuthentication,
    assistant_service: CurrentAssistantService,
) -> DataEnvelope[ConfirmActionResponse] | JSONResponse:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/assistant/actions/{action_id}/confirm"

    command = ConfirmActionCommand(
        trip_id=trip_id,
        action_id=action_id,
        requester_id=str(current_user.user_id),
    )

    result = await assistant_service.confirm_action(command)

    if isinstance(result, Failure):
        return map_assistant_failure(
            result.error, trace_id=trace_id, instance=instance
        )

    dto = result.value
    pa_schema = ProposedActionSchema(
        action_id=dto.action.action_id,
        trip_id=dto.action.trip_id,
        action_type=dto.action.action_type,
        summary=dto.action.summary,
        description=dto.action.description,
        payload=dto.action.payload,
        status=dto.action.status,
        created_at=dto.action.created_at,
        applied_at=dto.action.applied_at,
    )

    itinerary_schema = None
    if dto.itinerary:
        itinerary_schema = ItineraryResponse(
            itinerary_id=dto.itinerary.itinerary_id,
            trip_id=dto.itinerary.trip_id,
            version=dto.itinerary.version,
            created_at=dto.itinerary.created_at,
            updated_at=dto.itinerary.updated_at,
            days=[
                {
                    "day_id": d.day_id,
                    "day_number": d.day_number,
                    "title": d.title,
                    "date": d.date,
                    "created_at": d.created_at,
                    "updated_at": d.updated_at,
                    "items": [
                        {
                            "item_id": it.item_id,
                            "day_id": it.day_id,
                            "title": it.title,
                            "item_type": it.item_type,
                            "description": it.description,
                            "start_time": it.start_time,
                            "end_time": it.end_time,
                            "location_id": it.location_id,
                            "cost": it.cost,
                            "currency": it.currency,
                            "created_at": it.created_at,
                            "updated_at": it.updated_at,
                        }
                        for it in d.items
                    ],
                }
                for d in dto.itinerary.days
            ],
        )

    expense_schema = None
    if dto.expense:
        expense_schema = ExpenseResponse(
            expense_id=dto.expense.expense_id,
            category_id=dto.expense.category_id,
            title=dto.expense.title,
            amount=dto.expense.amount,
            currency=dto.expense.currency,
            expense_type=dto.expense.expense_type,
            description=dto.expense.description,
            expense_date=dto.expense.expense_date,
            created_at=dto.expense.created_at,
            updated_at=dto.expense.updated_at,
        )

    budget_schema = None
    if dto.budget:
        budget_schema = BudgetResponse(
            budget_id=dto.budget.budget_id,
            trip_id=dto.budget.trip_id,
            owner_id=dto.budget.owner_id,
            currency=dto.budget.currency,
            limit_amount=dto.budget.limit_amount,
            total_spent=dto.budget.total_spent,
            remaining_budget=dto.budget.remaining_budget,
            spent_percentage=dto.budget.spent_percentage,
            is_over_budget=dto.budget.is_over_budget,
            status=dto.budget.status,
            categories=[
                {
                    "category_id": c.category_id,
                    "name": c.name,
                    "allocated_amount": c.allocated_amount,
                    "description": c.description,
                    "total_spent": c.total_spent,
                }
                for c in dto.budget.categories
            ],
            created_at=dto.budget.created_at,
            updated_at=dto.budget.updated_at,
        )

    response_data = ConfirmActionResponse(
        action=pa_schema,
        itinerary=itinerary_schema,
        expense=expense_schema,
        budget=budget_schema,
        message=dto.message,
    )

    return DataEnvelope(data=response_data)


@router.post(
    "/{trip_id}/assistant/actions/{action_id}/reject",
    response_model=DataEnvelope[RejectActionResponse],
    status_code=status.HTTP_200_OK,
    summary="Reject/Cancel Proposed Action",
    description="Rejects a pending AI-proposed action without making any changes to the trip.",
)
async def reject_action(
    trip_id: str,
    action_id: str,
    current_user: RequireAuthentication,
    assistant_service: CurrentAssistantService,
) -> DataEnvelope[RejectActionResponse] | JSONResponse:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/assistant/actions/{action_id}/reject"

    command = RejectActionCommand(
        trip_id=trip_id,
        action_id=action_id,
        requester_id=str(current_user.user_id),
    )

    result = await assistant_service.reject_action(command)

    if isinstance(result, Failure):
        return map_assistant_failure(
            result.error, trace_id=trace_id, instance=instance
        )

    dto = result.value
    pa_schema = ProposedActionSchema(
        action_id=dto.action.action_id,
        trip_id=dto.action.trip_id,
        action_type=dto.action.action_type,
        summary=dto.action.summary,
        description=dto.action.description,
        payload=dto.action.payload,
        status=dto.action.status,
        created_at=dto.action.created_at,
        applied_at=dto.action.applied_at,
    )

    response_data = RejectActionResponse(
        action=pa_schema,
        message=dto.message,
    )

    return DataEnvelope(data=response_data)


@router.get(
    "/{trip_id}/warnings",
    response_model=DataEnvelope[TripWarningsResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Proactive Travel Warnings",
    description="Evaluate and retrieve proactive travel intelligence warnings (schedule conflicts, feasibility/transit issues, budget risks) for a trip. Accessible to Owners, Editors, and Viewers.",
)
@router.get(
    "/{trip_id}/assistant/warnings",
    response_model=DataEnvelope[TripWarningsResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def get_trip_warnings(
    trip_id: str,
    current_user: RequireAuthentication,
    assistant_service: CurrentAssistantService,
) -> DataEnvelope[TripWarningsResponse] | JSONResponse:
    trace_id = get_request_id() or ""
    instance = f"/api/v1/trips/{trip_id}/warnings"

    result = await assistant_service.get_warnings(
        trip_id=trip_id,
        requester_id=str(current_user.user_id),
    )

    if isinstance(result, Failure):
        return map_assistant_failure(
            result.error, trace_id=trace_id, instance=instance
        )

    dto = result.value
    warnings_schema = [
        TravelWarningSchema(
            warning_id=w.warning_id,
            category=w.category,
            severity=w.severity,
            title=w.title,
            message=w.message,
            day_number=w.day_number,
            item_ids=list(w.item_ids),
            metadata=w.metadata,
        )
        for w in dto.warnings
    ]

    response_data = TripWarningsResponse(
        trip_id=dto.trip_id,
        warnings=warnings_schema,
        total_warnings=dto.total_warnings,
        has_critical=dto.has_critical,
        itinerary_conflicts_count=dto.itinerary_conflicts_count,
        budget_risks_count=dto.budget_risks_count,
    )

    return DataEnvelope(data=response_data)
