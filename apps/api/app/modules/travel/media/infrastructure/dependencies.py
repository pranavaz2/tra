"""Media Infrastructure Layer — Dependency Injection Containers."""

from __future__ import annotations

import logging
from functools import lru_cache
from types import TracebackType
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import DatabaseSession
from app.modules.identity.authentication.infrastructure.event_publisher import (
    LoggingEventPublisher,
)
from app.modules.travel.budget.infrastructure.dependencies import CurrentBudgetRepository
from app.modules.travel.itinerary.infrastructure.dependencies import (
    CurrentItineraryRepository,
)
from app.modules.travel.media.application.handlers import (
    AttachMediaToActivityHandler,
    AttachMediaToExpenseHandler,
    DeleteMediaHandler,
    GetMediaByActivityHandler,
    GetMediaByExpenseHandler,
    GetMediaHandler,
    ListMediaHandler,
    UpdateCaptionHandler,
    UploadMediaHandler,
)
from app.modules.travel.media.application.media_service import MediaService
from app.modules.travel.media.domain.repositories.interfaces import (
    IMediaCollectionRepository,
)
from app.modules.travel.media.domain.services.interfaces import (
    ImageMetadataExtractor,
    StorageProvider,
    ThumbnailGenerator,
    VirusScanner,
)
from app.modules.travel.media.infrastructure.repositories.media_repository import (
    SQLAlchemyMediaCollectionRepository,
)
from app.modules.travel.trips.infrastructure.dependencies import CurrentTripRepository
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider
from app.shared.infrastructure.clock import Clock, SystemClock

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────── #
# Stub Providers (For local compilation/dev)                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class StubStorageProvider:
    """Stub StorageProvider implementation for local development."""

    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        mime_type: str,
    ) -> str:
        # Returns a mock HTTPS URL as required by the business rule
        return f"https://storage.travix.ai/{destination_path}"

    async def delete_file(self, file_url: str) -> None:
        pass


class StubThumbnailGenerator:
    """Stub ThumbnailGenerator implementation for local development."""

    async def generate_thumbnail(
        self,
        image_content: bytes,
        width: int,
        height: int,
        mime_type: str,
    ) -> bytes:
        return b"stub_thumbnail_bytes"


class StubVirusScanner:
    """Stub VirusScanner implementation that marks all files as clean."""

    async def scan_file(self, file_content: bytes) -> bool:
        return True


class StubImageMetadataExtractor:
    """Stub ImageMetadataExtractor returning standard image dimensions."""

    async def extract_metadata(
        self,
        file_content: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        return {"width": 800, "height": 600}


# ──────────────────────────────────────────────────────────────────────────── #
# Session-bound Unit of Work                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


class _SessionBoundUnitOfWork:
    """UnitOfWork that wraps an existing request-scoped AsyncSession."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def __aenter__(self) -> _SessionBoundUnitOfWork:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self._session.rollback()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()


# ──────────────────────────────────────────────────────────────────────────── #
# Singletons                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


@lru_cache(maxsize=1)
def _build_media_event_publisher() -> LoggingEventPublisher:
    return LoggingEventPublisher()


def get_media_event_publisher() -> EventPublisher:
    return _build_media_event_publisher()


@lru_cache(maxsize=1)
def _build_media_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_media_uuid_provider() -> UUIDProvider:
    return _build_media_uuid_provider()


@lru_cache(maxsize=1)
def _build_media_clock() -> SystemClock:
    return SystemClock()


def get_media_clock() -> Clock:
    return _build_media_clock()


# External provider singletons
@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    return StubStorageProvider()


@lru_cache(maxsize=1)
def get_thumbnail_generator() -> ThumbnailGenerator:
    return StubThumbnailGenerator()


@lru_cache(maxsize=1)
def get_virus_scanner() -> VirusScanner:
    return StubVirusScanner()


@lru_cache(maxsize=1)
def get_metadata_extractor() -> ImageMetadataExtractor:
    return StubImageMetadataExtractor()


CurrentMediaEventPublisher = Annotated[EventPublisher, Depends(get_media_event_publisher)]
CurrentMediaUUIDProvider = Annotated[UUIDProvider, Depends(get_media_uuid_provider)]
CurrentMediaClock = Annotated[Clock, Depends(get_media_clock)]

CurrentStorageProvider = Annotated[StorageProvider, Depends(get_storage_provider)]
CurrentThumbnailGenerator = Annotated[ThumbnailGenerator, Depends(get_thumbnail_generator)]
CurrentVirusScanner = Annotated[VirusScanner, Depends(get_virus_scanner)]
CurrentMetadataExtractor = Annotated[ImageMetadataExtractor, Depends(get_metadata_extractor)]


# ──────────────────────────────────────────────────────────────────────────── #
# Per-request dependencies                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_media_repository(db: DatabaseSession) -> IMediaCollectionRepository:
    return SQLAlchemyMediaCollectionRepository(db)


def get_media_unit_of_work(db: DatabaseSession) -> UnitOfWork:
    return _SessionBoundUnitOfWork(db)


CurrentMediaRepository = Annotated[IMediaCollectionRepository, Depends(get_media_repository)]
CurrentMediaUnitOfWork = Annotated[UnitOfWork, Depends(get_media_unit_of_work)]


# ──────────────────────────────────────────────────────────────────────────── #
# MediaService                                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


def get_media_service(
    repository: CurrentMediaRepository,
    trip_repository: CurrentTripRepository,
    itinerary_repository: CurrentItineraryRepository,
    budget_repository: CurrentBudgetRepository,
    storage_provider: CurrentStorageProvider,
    thumbnail_generator: CurrentThumbnailGenerator,
    virus_scanner: CurrentVirusScanner,
    metadata_extractor: CurrentMetadataExtractor,
    uow: CurrentMediaUnitOfWork,
    event_publisher: CurrentMediaEventPublisher,
    uuid_provider: CurrentMediaUUIDProvider,
    clock: CurrentMediaClock,
) -> MediaService:
    return MediaService(
        repository=repository,
        trip_repository=trip_repository,
        itinerary_repository=itinerary_repository,
        budget_repository=budget_repository,
        storage_provider=storage_provider,
        thumbnail_generator=thumbnail_generator,
        virus_scanner=virus_scanner,
        metadata_extractor=metadata_extractor,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=uuid_provider,
        clock=clock,
    )


CurrentMediaService = Annotated[MediaService, Depends(get_media_service)]


# ──────────────────────────────────────────────────────────────────────────── #
# Handlers                                                                       #
# ──────────────────────────────────────────────────────────────────────────── #


def get_upload_media_handler(service: CurrentMediaService) -> UploadMediaHandler:
    return UploadMediaHandler(service)


def get_update_caption_handler(service: CurrentMediaService) -> UpdateCaptionHandler:
    return UpdateCaptionHandler(service)


def get_delete_media_handler(service: CurrentMediaService) -> DeleteMediaHandler:
    return DeleteMediaHandler(service)


def get_attach_media_to_activity_handler(
    service: CurrentMediaService,
) -> AttachMediaToActivityHandler:
    return AttachMediaToActivityHandler(service)


def get_attach_media_to_expense_handler(
    service: CurrentMediaService,
) -> AttachMediaToExpenseHandler:
    return AttachMediaToExpenseHandler(service)


def get_get_media_handler(service: CurrentMediaService) -> GetMediaHandler:
    return GetMediaHandler(service)


def get_list_media_handler(service: CurrentMediaService) -> ListMediaHandler:
    return ListMediaHandler(service)


def get_media_by_activity_handler(
    service: CurrentMediaService,
) -> GetMediaByActivityHandler:
    return GetMediaByActivityHandler(service)


def get_media_by_expense_handler(
    service: CurrentMediaService,
) -> GetMediaByExpenseHandler:
    return GetMediaByExpenseHandler(service)


CurrentUploadMediaHandler = Annotated[UploadMediaHandler, Depends(get_upload_media_handler)]
CurrentUpdateCaptionHandler = Annotated[UpdateCaptionHandler, Depends(get_update_caption_handler)]
CurrentDeleteMediaHandler = Annotated[DeleteMediaHandler, Depends(get_delete_media_handler)]
CurrentAttachMediaToActivityHandler = Annotated[
    AttachMediaToActivityHandler, Depends(get_attach_media_to_activity_handler)
]
CurrentAttachMediaToExpenseHandler = Annotated[
    AttachMediaToExpenseHandler, Depends(get_attach_media_to_expense_handler)
]
CurrentGetMediaHandler = Annotated[GetMediaHandler, Depends(get_get_media_handler)]
CurrentListMediaHandler = Annotated[ListMediaHandler, Depends(get_list_media_handler)]
CurrentGetMediaByActivityHandler = Annotated[
    GetMediaByActivityHandler, Depends(get_media_by_activity_handler)
]
CurrentGetMediaByExpenseHandler = Annotated[
    GetMediaByExpenseHandler, Depends(get_media_by_expense_handler)
]
