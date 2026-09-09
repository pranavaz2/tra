"""Assistant Infrastructure Layer — Dependency Injection Containers."""

from __future__ import annotations

from functools import lru_cache
import logging
from typing import Annotated, Any

from fastapi import Depends

from app.config import get_settings
from app.dependencies import DatabaseSession
from app.modules.travel.assistant.application.services.assistant_context_builder import (
    AssistantContextBuilder,
)
from app.modules.travel.assistant.application.services.assistant_service import (
    AssistantService,
)
from app.modules.travel.assistant.domain.repositories.conversation_repository import (
    IAssistantConversationRepository,
)
from app.modules.travel.assistant.domain.repositories.interfaces import (
    IProposedActionRepository,
)
from app.modules.travel.assistant.infrastructure.engine.base import AssistantEngine
from app.modules.travel.assistant.infrastructure.engine.gemini_assistant_engine import (
    GeminiAssistantEngine,
)
from app.modules.travel.assistant.infrastructure.engine.mock_assistant_engine import (
    MockAssistantEngine,
)
from app.modules.travel.assistant.infrastructure.repositories.conversation_repository_impl import (
    InMemoryAssistantConversationRepository,
    SQLAlchemyAssistantConversationRepository,
)
from app.modules.travel.assistant.infrastructure.repositories.in_memory_action_repo import (
    InMemoryProposedActionRepository,
)
from app.modules.travel.budget.application.budget_service import BudgetService
from app.modules.travel.budget.infrastructure.dependencies import (
    CurrentBudgetRepository,
    CurrentBudgetService,
)
from app.modules.travel.itinerary.infrastructure.dependencies import (
    CurrentItineraryRepository,
    CurrentItineraryService,
    CurrentItineraryUUIDProvider,
)
from app.modules.travel.media.infrastructure.dependencies import (
    CurrentMediaRepository,
)
from app.modules.travel.sharing.infrastructure.dependencies import (
    CurrentCollaborationRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import (
    CurrentTripRepository,
)
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider

logger = logging.getLogger(__name__)

# Singleton In-memory Action Repository (for pending action states)
_in_memory_action_repo = InMemoryProposedActionRepository()


def get_proposed_action_repository() -> IProposedActionRepository:
    return _in_memory_action_repo


CurrentProposedActionRepository = Annotated[
    IProposedActionRepository, Depends(get_proposed_action_repository)
]


def get_assistant_conversation_repository(
    db: DatabaseSession,
) -> IAssistantConversationRepository:
    return SQLAlchemyAssistantConversationRepository(db)


CurrentAssistantConversationRepository = Annotated[
    IAssistantConversationRepository, Depends(get_assistant_conversation_repository)
]


from app.services.maps.factory import get_places_provider, get_routing_provider


def get_assistant_engine() -> AssistantEngine:
    settings = get_settings()
    places_provider = get_places_provider()
    routing_provider = get_routing_provider()
    if settings.ai_provider == "gemini":
        key = settings.gemini_api_key or settings.ai_api_key
        if key:
            return GeminiAssistantEngine(
                api_key=key.get_secret_value(),
                places_provider=places_provider,
                routing_provider=routing_provider,
                model=settings.ai_model or "gemini-2.0-flash",
                timeout_seconds=float(settings.ai_timeout_seconds),
                temperature=float(settings.ai_temperature),
                max_output_tokens=settings.ai_max_tokens,
                max_retries=settings.ai_max_retries,
            )
    return MockAssistantEngine(
        places_provider=places_provider,
        routing_provider=routing_provider,
    )



CurrentAssistantEngine = Annotated[AssistantEngine, Depends(get_assistant_engine)]



def get_assistant_context_builder(
    trip_repository: CurrentTripRepository,
    itinerary_repository: CurrentItineraryRepository,
    budget_repository: CurrentBudgetRepository,
    collaboration_repository: CurrentCollaborationRepository,
    media_repository: CurrentMediaRepository,
) -> AssistantContextBuilder:
    return AssistantContextBuilder(
        trip_repository=trip_repository,
        itinerary_repository=itinerary_repository,
        budget_repository=budget_repository,
        collaboration_repository=collaboration_repository,
        media_repository=media_repository,
    )


CurrentAssistantContextBuilder = Annotated[
    AssistantContextBuilder, Depends(get_assistant_context_builder)
]


def get_assistant_service(
    assistant_engine: CurrentAssistantEngine,
    context_builder: CurrentAssistantContextBuilder,
    action_repository: CurrentProposedActionRepository,
    conversation_repository: CurrentAssistantConversationRepository,
    trip_repository: CurrentTripRepository,
    collaboration_repository: CurrentCollaborationRepository,
    itinerary_service: CurrentItineraryService,
    budget_service: CurrentBudgetService,
    budget_repository: CurrentBudgetRepository,
    uuid_provider: CurrentItineraryUUIDProvider,
) -> AssistantService:
    return AssistantService(
        assistant_engine=assistant_engine,
        context_builder=context_builder,
        action_repository=action_repository,
        conversation_repository=conversation_repository,
        trip_repository=trip_repository,
        collaboration_repository=collaboration_repository,
        itinerary_service=itinerary_service,
        budget_service=budget_service,
        budget_repository=budget_repository,
        uuid_provider=uuid_provider,
    )


CurrentAssistantService = Annotated[AssistantService, Depends(get_assistant_service)]


def get_proactive_intelligence_service(
    itinerary_repository: CurrentItineraryRepository,
    budget_repository: CurrentBudgetRepository,
) -> ProactiveIntelligenceService:
    from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
        ProactiveIntelligenceService,
    )
    return ProactiveIntelligenceService(
        itinerary_repository=itinerary_repository,
        budget_repository=budget_repository,
    )


CurrentProactiveIntelligenceService = Annotated[
    Any, Depends(get_proactive_intelligence_service)
]
