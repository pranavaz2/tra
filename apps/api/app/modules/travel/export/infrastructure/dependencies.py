"""Export dependency injection."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.dependencies import DatabaseSession
from app.modules.travel.budget.infrastructure.repositories.budget_repository import (
    SQLAlchemyTripBudgetRepository,
)
from app.modules.travel.export.application.export_service import ExportService
from app.modules.travel.itinerary.infrastructure.repositories.itinerary_repository import (
    SQLAlchemyItineraryRepository,
)
from app.modules.travel.sharing.infrastructure.repositories.sharing_repository import (
    SQLAlchemyTripCollaborationRepository,
)
from app.modules.travel.trips.infrastructure.repositories.trip_repository import (
    SQLAlchemyTripRepository,
)


def get_export_service(
    session: DatabaseSession,
) -> ExportService:
    """Return ExportService wired with repositories."""
    trip_repo = SQLAlchemyTripRepository(session)
    itinerary_repo = SQLAlchemyItineraryRepository(session)
    budget_repo = SQLAlchemyTripBudgetRepository(session)
    sharing_repo = SQLAlchemyTripCollaborationRepository(session)

    return ExportService(
        trip_repository=trip_repo,
        itinerary_repository=itinerary_repo,
        budget_repository=budget_repo,
        trip_sharing_repository=sharing_repo,
    )


CurrentExportService = Annotated[ExportService, Depends(get_export_service)]
