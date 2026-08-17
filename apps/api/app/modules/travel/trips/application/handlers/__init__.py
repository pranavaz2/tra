"""
Trip CQRS command and query handlers.

Each handler is a thin delegation wrapper around TripService. Separating
handlers from the service enables:
  - Cross-cutting concerns (structured logging, metrics, tracing) to be
    applied at the handler boundary without polluting the service.
  - Multiple dispatch paths (HTTP, CLI, background worker) to share the
    same handler class without coupling to any framework.
  - A future command bus to dispatch by type without coupling to the service.

Current implementation: all handlers delegate entirely to TripService and
own no business logic of their own.

Handler naming convention (per CLAUDE.md §8):
  PascalCase + Handler suffix.

Usage (FastAPI route — future):
    handler = Depends(get_create_trip_handler)

    @router.post("/trips")
    async def create_trip(
        body: TripCreateRequest,
        current_user: AuthenticatedUser,
        handler: CreateTripHandler,
    ) -> TripResponse:
        command = CreateTripCommand(owner_id=str(current_user.user_id), title=body.title)
        result = await handler.handle(command)
        match result:
            case Success(value=summary):
                return TripResponse.from_summary(summary)
            case Failure(error=err):
                raise_http_for(err)
"""

from __future__ import annotations

import logging

from app.modules.travel.trips.application.commands import (
    CreateTripCommand,
    DeleteTripCommand,
    UpdateTripCommand,
)
from app.modules.travel.trips.application.dtos import (
    CreateTripResult,
    DeleteTripResult,
    GetTripResult,
    ListTripsResult,
    UpdateTripResult,
)
from app.modules.travel.trips.application.queries import GetTripQuery, ListTripsQuery
from app.modules.travel.trips.application.trip_service import TripService

logger = logging.getLogger(__name__)


class CreateTripHandler:
    """
    CQRS handler for CreateTripCommand.

    Delegates to TripService.create_trip(). Returns CreateTripResult
    (Success[TripSummary] | Failure[TravixError]).
    """

    def __init__(self, service: TripService) -> None:
        self._service = service

    async def handle(self, command: CreateTripCommand) -> CreateTripResult:
        """Handle a CreateTripCommand and return the result."""
        logger.debug(
            "Handling CreateTripCommand",
            extra={"owner_id": command.owner_id, "title_len": len(command.title)},
        )
        return await self._service.create_trip(command)


class UpdateTripHandler:
    """
    CQRS handler for UpdateTripCommand.

    Delegates to TripService.update_trip(). Returns UpdateTripResult
    (Success[TripSummary] | Failure[TravixError]).
    """

    def __init__(self, service: TripService) -> None:
        self._service = service

    async def handle(self, command: UpdateTripCommand) -> UpdateTripResult:
        """Handle an UpdateTripCommand and return the result."""
        logger.debug(
            "Handling UpdateTripCommand",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )
        return await self._service.update_trip(command)


class DeleteTripHandler:
    """
    CQRS handler for DeleteTripCommand.

    Delegates to TripService.delete_trip(). Returns DeleteTripResult
    (Success[None] | Failure[TravixError]).
    """

    def __init__(self, service: TripService) -> None:
        self._service = service

    async def handle(self, command: DeleteTripCommand) -> DeleteTripResult:
        """Handle a DeleteTripCommand and return the result."""
        logger.debug(
            "Handling DeleteTripCommand",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )
        return await self._service.delete_trip(command)


class GetTripHandler:
    """
    CQRS handler for GetTripQuery.

    Delegates to TripService.get_trip(). Returns GetTripResult
    (Success[TripSummary] | Failure[TravixError]).
    """

    def __init__(self, service: TripService) -> None:
        self._service = service

    async def handle(self, query: GetTripQuery) -> GetTripResult:
        """Handle a GetTripQuery and return the result."""
        logger.debug(
            "Handling GetTripQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.get_trip(query)


class ListTripsHandler:
    """
    CQRS handler for ListTripsQuery.

    Delegates to TripService.list_trips(). Returns ListTripsResult
    (Success[TripListPage] | Failure[TravixError]).
    """

    def __init__(self, service: TripService) -> None:
        self._service = service

    async def handle(self, query: ListTripsQuery) -> ListTripsResult:
        """Handle a ListTripsQuery and return the result."""
        logger.debug(
            "Handling ListTripsQuery",
            extra={"owner_id": query.owner_id, "limit": query.limit},
        )
        return await self._service.list_trips(query)
