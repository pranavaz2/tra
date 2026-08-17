"""Itinerary CQRS command and query handlers."""

from __future__ import annotations

import logging

from app.modules.travel.itinerary.application.commands import (
    AddItineraryDayCommand,
    AddItineraryItemCommand,
    CreateItineraryCommand,
    RemoveItineraryDayCommand,
    RemoveItineraryItemCommand,
    UpdateItineraryDayCommand,
    UpdateItineraryItemCommand,
)
from app.modules.travel.itinerary.application.dtos import (
    AddItineraryDayResult,
    AddItineraryItemResult,
    CreateItineraryResult,
    GetItineraryResult,
    RemoveItineraryDayResult,
    RemoveItineraryItemResult,
    UpdateItineraryDayResult,
    UpdateItineraryItemResult,
)
from app.modules.travel.itinerary.application.itinerary_service import ItineraryService
from app.modules.travel.itinerary.application.queries import GetItineraryQuery

logger = logging.getLogger(__name__)


class CreateItineraryHandler:
    """CQRS handler for CreateItineraryCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: CreateItineraryCommand) -> CreateItineraryResult:
        logger.debug(
            "Handling CreateItineraryCommand",
            extra={"trip_id": command.trip_id, "requester_id": command.requester_id},
        )
        return await self._service.create_itinerary(command)


class AddItineraryDayHandler:
    """CQRS handler for AddItineraryDayCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: AddItineraryDayCommand) -> AddItineraryDayResult:
        logger.debug(
            "Handling AddItineraryDayCommand",
            extra={
                "trip_id": command.trip_id,
                "requester_id": command.requester_id,
                "day_number": command.day_number,
            },
        )
        return await self._service.add_day(command)


class UpdateItineraryDayHandler:
    """CQRS handler for UpdateItineraryDayCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: UpdateItineraryDayCommand) -> UpdateItineraryDayResult:
        logger.debug(
            "Handling UpdateItineraryDayCommand",
            extra={
                "trip_id": command.trip_id,
                "day_id": command.day_id,
                "requester_id": command.requester_id,
            },
        )
        return await self._service.update_day(command)


class RemoveItineraryDayHandler:
    """CQRS handler for RemoveItineraryDayCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: RemoveItineraryDayCommand) -> RemoveItineraryDayResult:
        logger.debug(
            "Handling RemoveItineraryDayCommand",
            extra={
                "trip_id": command.trip_id,
                "day_id": command.day_id,
                "requester_id": command.requester_id,
            },
        )
        return await self._service.remove_day(command)


class AddItineraryItemHandler:
    """CQRS handler for AddItineraryItemCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: AddItineraryItemCommand) -> AddItineraryItemResult:
        logger.debug(
            "Handling AddItineraryItemCommand",
            extra={
                "trip_id": command.trip_id,
                "day_id": command.day_id,
                "requester_id": command.requester_id,
            },
        )
        return await self._service.add_item(command)


class UpdateItineraryItemHandler:
    """CQRS handler for UpdateItineraryItemCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: UpdateItineraryItemCommand) -> UpdateItineraryItemResult:
        logger.debug(
            "Handling UpdateItineraryItemCommand",
            extra={
                "trip_id": command.trip_id,
                "item_id": command.item_id,
                "requester_id": command.requester_id,
            },
        )
        return await self._service.update_item(command)


class RemoveItineraryItemHandler:
    """CQRS handler for RemoveItineraryItemCommand."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, command: RemoveItineraryItemCommand) -> RemoveItineraryItemResult:
        logger.debug(
            "Handling RemoveItineraryItemCommand",
            extra={
                "trip_id": command.trip_id,
                "item_id": command.item_id,
                "requester_id": command.requester_id,
            },
        )
        return await self._service.remove_item(command)


class GetItineraryHandler:
    """CQRS handler for GetItineraryQuery."""

    def __init__(self, service: ItineraryService) -> None:
        self._service = service

    async def handle(self, query: GetItineraryQuery) -> GetItineraryResult:
        logger.debug(
            "Handling GetItineraryQuery",
            extra={"trip_id": query.trip_id, "requester_id": query.requester_id},
        )
        return await self._service.get_itinerary(query)
