"""Media CQRS command and query handlers."""

from __future__ import annotations

import logging

from app.modules.travel.media.application.commands import (
    AttachMediaToActivityCommand,
    AttachMediaToExpenseCommand,
    DeleteMediaCommand,
    UpdateCaptionCommand,
    UploadMediaCommand,
)
from app.modules.travel.media.application.dtos import (
    AttachMediaToActivityResult,
    AttachMediaToExpenseResult,
    DeleteMediaResult,
    GetMediaByActivityResult,
    GetMediaByExpenseResult,
    GetMediaResult,
    ListMediaResult,
    UpdateCaptionResult,
    UploadMediaResult,
)
from app.modules.travel.media.application.media_service import MediaService
from app.modules.travel.media.application.queries import (
    GetMediaByActivityQuery,
    GetMediaByExpenseQuery,
    GetMediaQuery,
    ListMediaQuery,
)

logger = logging.getLogger(__name__)


class UploadMediaHandler:
    """CQRS handler for UploadMediaCommand."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, command: UploadMediaCommand) -> UploadMediaResult:
        logger.debug(
            "Handling UploadMediaCommand",
            extra={"trip_id": command.trip_id, "file_name": command.file_name},
        )
        return await self._service.upload_media(command)


class UpdateCaptionHandler:
    """CQRS handler for UpdateCaptionCommand."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, command: UpdateCaptionCommand) -> UpdateCaptionResult:
        logger.debug(
            "Handling UpdateCaptionCommand",
            extra={"trip_id": command.trip_id, "media_id": command.media_id},
        )
        return await self._service.update_caption(command)


class DeleteMediaHandler:
    """CQRS handler for DeleteMediaCommand."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, command: DeleteMediaCommand) -> DeleteMediaResult:
        logger.debug(
            "Handling DeleteMediaCommand",
            extra={"trip_id": command.trip_id, "media_id": command.media_id},
        )
        return await self._service.delete_media(command)


class AttachMediaToActivityHandler:
    """CQRS handler for AttachMediaToActivityCommand."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, command: AttachMediaToActivityCommand) -> AttachMediaToActivityResult:
        logger.debug(
            "Handling AttachMediaToActivityCommand",
            extra={
                "trip_id": command.trip_id,
                "media_id": command.media_id,
                "activity_id": command.activity_id,
            },
        )
        return await self._service.attach_to_activity(command)


class AttachMediaToExpenseHandler:
    """CQRS handler for AttachMediaToExpenseCommand."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, command: AttachMediaToExpenseCommand) -> AttachMediaToExpenseResult:
        logger.debug(
            "Handling AttachMediaToExpenseCommand",
            extra={
                "trip_id": command.trip_id,
                "media_id": command.media_id,
                "expense_id": command.expense_id,
            },
        )
        return await self._service.attach_to_expense(command)


class GetMediaHandler:
    """CQRS handler for GetMediaQuery."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, query: GetMediaQuery) -> GetMediaResult:
        logger.debug(
            "Handling GetMediaQuery",
            extra={"trip_id": query.trip_id, "media_id": query.media_id},
        )
        return await self._service.get_media(query)


class ListMediaHandler:
    """CQRS handler for ListMediaQuery."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, query: ListMediaQuery) -> ListMediaResult:
        logger.debug(
            "Handling ListMediaQuery",
            extra={"trip_id": query.trip_id, "limit": query.limit},
        )
        return await self._service.list_media(query)


class GetMediaByActivityHandler:
    """CQRS handler for GetMediaByActivityQuery."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, query: GetMediaByActivityQuery) -> GetMediaByActivityResult:
        logger.debug(
            "Handling GetMediaByActivityQuery",
            extra={"trip_id": query.trip_id, "activity_id": query.activity_id},
        )
        return await self._service.get_media_by_activity(query)


class GetMediaByExpenseHandler:
    """CQRS handler for GetMediaByExpenseQuery."""

    def __init__(self, service: MediaService) -> None:
        self._service = service

    async def handle(self, query: GetMediaByExpenseQuery) -> GetMediaByExpenseResult:
        logger.debug(
            "Handling GetMediaByExpenseQuery",
            extra={"trip_id": query.trip_id, "expense_id": query.expense_id},
        )
        return await self._service.get_media_by_expense(query)
