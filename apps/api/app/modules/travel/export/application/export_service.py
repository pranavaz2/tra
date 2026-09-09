"""Export application service."""

from __future__ import annotations

import logging
import uuid

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.repositories.interfaces import (
    ITripBudgetRepository,
)
from app.modules.travel.export.infrastructure.ical_generator import ICalGenerator
from app.modules.travel.export.infrastructure.pdf_generator import PdfGenerator
from app.modules.travel.itinerary.domain.repositories.interfaces import (
    IItineraryRepository,
)
from app.modules.travel.sharing.domain.repositories.interfaces import (
    ITripCollaborationRepository,
)
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import ForbiddenError, NotFoundError
from app.shared.domain.result import Failure, Result, Success

logger = logging.getLogger(__name__)


class ExportService:
    """Orchestrates iCal and PDF export workflows with authorization checks."""

    def __init__(
        self,
        *,
        trip_repository: ITripRepository,
        itinerary_repository: IItineraryRepository,
        budget_repository: ITripBudgetRepository,
        trip_sharing_repository: ITripCollaborationRepository,
    ) -> None:
        self._trip_repo = trip_repository
        self._itinerary_repo = itinerary_repository
        self._budget_repo = budget_repository
        self._sharing_repo = trip_sharing_repository

    async def _verify_access_and_get_trip(
        self, trip_id: TripId, user_id: UserId
    ) -> tuple[bool, Any]:
        trip = await self._trip_repo.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return False, None

        if trip.owner_id == user_id:
            return True, trip

        collab = await self._sharing_repo.find_by_trip_id(trip_id)
        if collab:
            for member in collab.members:
                if member.user_id == user_id:
                    return True, trip
            if getattr(collab, "is_public", False):
                return True, trip

        if getattr(trip, "privacy", None) and trip.privacy.value == "public":
            return True, trip

        return False, None

    async def export_ical(
        self,
        *,
        trip_id_str: str,
        requester_id_str: str,
    ) -> Result[str]:
        """Export trip itinerary as RFC 5545 iCalendar format."""
        try:
            trip_uuid = uuid.UUID(trip_id_str)
            user_uuid = uuid.UUID(requester_id_str)
        except ValueError:
            return Failure(NotFoundError("Trip not found"))

        trip_id = TripId(trip_uuid)
        user_id = UserId(user_uuid)

        has_access, trip = await self._verify_access_and_get_trip(trip_id, user_id)
        if not has_access or trip is None:
            return Failure(ForbiddenError("You do not have permission to export this trip"))

        itinerary = await self._itinerary_repo.find_by_trip_id(trip_id)
        ical_content = ICalGenerator.generate(trip=trip, itinerary=itinerary)
        return Success(ical_content)

    async def export_pdf(
        self,
        *,
        trip_id_str: str,
        requester_id_str: str,
    ) -> Result[bytes]:
        """Export trip itinerary and budget summary as a formatted PDF."""
        try:
            trip_uuid = uuid.UUID(trip_id_str)
            user_uuid = uuid.UUID(requester_id_str)
        except ValueError:
            return Failure(NotFoundError("Trip not found"))

        trip_id = TripId(trip_uuid)
        user_id = UserId(user_uuid)

        has_access, trip = await self._verify_access_and_get_trip(trip_id, user_id)
        if not has_access or trip is None:
            return Failure(ForbiddenError("You do not have permission to export this trip"))

        itinerary = await self._itinerary_repo.find_by_trip_id(trip_id)
        budget = await self._budget_repo.find_by_trip_id(trip_id)

        pdf_bytes = PdfGenerator.generate(
            trip=trip,
            itinerary=itinerary,
            budget=budget,
        )
        return Success(pdf_bytes)
