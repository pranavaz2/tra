"""Jobs module dependency injection."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.core.jobs.scheduler import AsyncioJobScheduler, IJobScheduler, JobConfig
from app.dependencies import DatabaseSession
from app.modules.travel.assistant.application.services.proactive_intelligence_service import (
    ProactiveIntelligenceService,
)
from app.modules.travel.assistant.infrastructure.dependencies import (
    get_proactive_intelligence_service,
)
from app.modules.travel.budget.infrastructure.repositories.budget_repository import (
    SQLAlchemyTripBudgetRepository,
)
from app.modules.travel.itinerary.infrastructure.repositories.itinerary_repository import (
    SQLAlchemyItineraryRepository,
)
from app.modules.travel.jobs.travel_intelligence_job import (
    ScheduledTravelIntelligenceJob,
)
from app.modules.travel.notifications.infrastructure.dependencies import (
    get_notification_service,
)
from app.modules.travel.notifications.application.notification_service import (
    NotificationService,
)
from app.modules.travel.sharing.infrastructure.repositories.sharing_repository import (
    SQLAlchemyTripCollaborationRepository,
)
from app.modules.travel.trips.infrastructure.repositories.trip_repository import (
    SQLAlchemyTripRepository,
)
from app.modules.travel.weather.domain.provider import IWeatherProvider
from app.modules.travel.weather.infrastructure.providers.open_meteo_provider import (
    OpenMeteoWeatherProvider,
)


@lru_cache(maxsize=1)
def get_global_scheduler() -> IJobScheduler:
    """Return the application singleton job scheduler."""
    scheduler = AsyncioJobScheduler()
    return scheduler


@lru_cache(maxsize=1)
def get_weather_provider() -> IWeatherProvider:
    """Return weather forecast provider."""
    return OpenMeteoWeatherProvider()


def get_travel_intelligence_job(
    session: DatabaseSession,
    notification_service: Annotated[NotificationService, Depends(get_notification_service)],
    weather_provider: Annotated[IWeatherProvider, Depends(get_weather_provider)],
    proactive_intelligence: Annotated[ProactiveIntelligenceService, Depends(get_proactive_intelligence_service)],
) -> ScheduledTravelIntelligenceJob:
    """Instantiate ScheduledTravelIntelligenceJob with scoped repositories."""
    trip_repo = SQLAlchemyTripRepository(session)
    itinerary_repo = SQLAlchemyItineraryRepository(session)
    budget_repo = SQLAlchemyTripBudgetRepository(session)
    sharing_repo = SQLAlchemyTripCollaborationRepository(session)

    return ScheduledTravelIntelligenceJob(
        trip_repository=trip_repo,
        itinerary_repository=itinerary_repo,
        budget_repository=budget_repo,
        sharing_repository=sharing_repo,
        notification_service=notification_service,
        weather_provider=weather_provider,
        proactive_intelligence=proactive_intelligence,
    )


CurrentTravelIntelligenceJob = Annotated[
    ScheduledTravelIntelligenceJob, Depends(get_travel_intelligence_job)
]
CurrentJobScheduler = Annotated[IJobScheduler, Depends(get_global_scheduler)]
