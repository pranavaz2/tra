"""MediaService — orchestrates all use cases for TripMediaCollection and files."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from app.core.pagination import decode_cursor, encode_cursor
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.repositories.interfaces import ITripBudgetRepository
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.itinerary.domain.repositories.interfaces import IItineraryRepository
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
    MediaItemSummary,
    MediaListPage,
    UpdateCaptionResult,
    UploadMediaResult,
)
from app.modules.travel.media.application.queries import (
    GetMediaByActivityQuery,
    GetMediaByExpenseQuery,
    GetMediaQuery,
    ListMediaQuery,
)
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.modules.travel.media.domain.enums.media_status import MediaStatus
from app.modules.travel.media.domain.enums.media_type import MediaType
from app.modules.travel.media.domain.errors import (
    MediaCollectionNotFoundError,
    MediaItemNotFoundError,
)
from app.modules.travel.media.domain.repositories.interfaces import (
    IMediaCollectionRepository,
)
from app.modules.travel.media.domain.services.interfaces import (
    ImageMetadataExtractor,
    StorageProvider,
    ThumbnailGenerator,
    VirusScanner,
)
from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl
from app.modules.travel.sharing.infrastructure.models.sharing_models import (
    TripCollaborationModel,
    TripMemberModel,
)
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import (
    ForbiddenError,
    InfrastructureError,
    TravixError,
    ValidationError,
)
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import UUIDProvider
from app.shared.infrastructure.clock import Clock

logger = logging.getLogger(__name__)


class MediaService:
    """Orchestrates all use cases for TripMediaCollection and file storage."""

    def __init__(
        self,
        *,
        repository: IMediaCollectionRepository,
        trip_repository: ITripRepository,
        itinerary_repository: IItineraryRepository,
        budget_repository: ITripBudgetRepository,
        storage_provider: StorageProvider,
        thumbnail_generator: ThumbnailGenerator,
        virus_scanner: VirusScanner,
        metadata_extractor: ImageMetadataExtractor,
        unit_of_work: UnitOfWork,
        event_publisher: EventPublisher,
        uuid_provider: UUIDProvider,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._trip_repository = trip_repository
        self._itinerary_repository = itinerary_repository
        self._budget_repository = budget_repository
        self._storage_provider = storage_provider
        self._thumbnail_generator = thumbnail_generator
        self._virus_scanner = virus_scanner
        self._metadata_extractor = metadata_extractor
        self._uow = unit_of_work
        self._event_publisher = event_publisher
        self._uuid_provider = uuid_provider
        self._clock = clock

    # ------------------------------------------------------------------ #
    # Helper: Authorization check                                          #
    # ------------------------------------------------------------------ #

    async def _check_access(self, trip_id: TripId, user_id: UserId, session: Any) -> bool:
        """Check if user is the trip owner or a collaborator."""
        trip = await self._trip_repository.find_by_id(trip_id)
        if trip is None or trip.is_deleted:
            return False

        if trip.owner_id == user_id:
            return True

        # Check collaboration members
        stmt = (
            select(TripMemberModel.id)
            .join(TripCollaborationModel)
            .where(
                TripCollaborationModel.trip_id == trip_id.value,
                TripMemberModel.user_id == user_id.value,
            )
        )
        res = await session.execute(stmt)
        return res.scalar() is not None

    # ------------------------------------------------------------------ #
    # Mutations                                                            #
    # ------------------------------------------------------------------ #

    async def upload_media(self, command: UploadMediaCommand) -> UploadMediaResult:
        """Upload file content, scan it, extract metadata, and save in TripMediaCollection."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            uploaded_by = UserId.from_str(command.uploaded_by)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        # 1. Scanner check
        try:
            is_clean = await self._virus_scanner.scan_file(command.file_content)
        except Exception as exc:
            return Failure(InfrastructureError("Virus scan failed.", cause=exc))

        if not is_clean:
            return Failure(
                ValidationError("Virus detected or scanner rejected the file.", field="file")
            )

        # 2. Extract metadata
        width = None
        height = None
        if command.mime_type.startswith("image/"):
            try:
                extracted = await self._metadata_extractor.extract_metadata(
                    command.file_content, command.mime_type
                )
                width = extracted.get("width")
                height = extracted.get("height")
            except Exception as exc:
                logger.warning(
                    "Metadata extraction failed. Continuing without dimensions.", exc_info=exc
                )

        media_id = MediaId(value=self._uuid_provider.generate())

        # 3. Upload to storage
        destination_path = f"trips/{trip_id}/media/{media_id}_{command.file_name}"
        try:
            url_str = await self._storage_provider.upload_file(
                command.file_content, destination_path, command.mime_type
            )
            url = MediaUrl(url_str)
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("File upload to storage failed.", cause=exc))

        metadata = MediaMetadata(
            mime_type=command.mime_type,
            size_bytes=len(command.file_content),
            file_name=command.file_name,
            width=width,
            height=height,
        )

        media_type = MediaType.NOTE
        if command.mime_type.startswith("image/"):
            media_type = MediaType.PHOTO
        elif command.mime_type.startswith("video/"):
            media_type = MediaType.VIDEO
        elif command.mime_type.startswith("audio/"):
            media_type = MediaType.VOICE_MEMO
        elif "receipt" in command.file_name.lower() or "invoice" in command.file_name.lower():
            media_type = MediaType.RECEIPT

        try:
            async with self._uow:
                # Share UoW session for custom select queries
                session = self._uow._session  # type: ignore[attr-defined]

                # Authorization check
                has_access = await self._check_access(trip_id, uploaded_by, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have access to upload media for this trip.")
                    )

                # Find or create TripMediaCollection
                collection = await self._repository.find_by_trip_id(trip_id)
                if collection is None:
                    collection_id = MediaCollectionId(value=self._uuid_provider.generate())
                    collection = TripMediaCollection.create(
                        collection_id=collection_id,
                        trip_id=trip_id,
                        owner_id=uploaded_by,
                    )

                media_item = collection.upload_media(
                    media_id=media_id,
                    url=url,
                    media_type=media_type,
                    metadata=metadata,
                    uploaded_by=uploaded_by,
                )

                await self._repository.save(collection)
                await self._uow.commit()
        except TravixError as exc:
            # Attempt to clean up uploaded file on domain/validation failure
            try:
                await self._storage_provider.delete_file(url_str)
            except Exception:
                logger.error("Cleanup of failed upload media file failed.")
            return Failure(exc)
        except Exception as exc:
            try:
                await self._storage_provider.delete_file(url_str)
            except Exception:
                logger.warning("Failed to clean up uploaded file after persistence failure.")
            return Failure(InfrastructureError("Failed to persist media reference.", cause=exc))

        await self._publish(collection.pop_events(), context="upload_media")
        return Success(MediaItemSummary.from_entity(media_item))

    async def update_caption(self, command: UpdateCaptionCommand) -> UpdateCaptionResult:
        """Update the caption of a media item."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            media_id = MediaId.from_str(command.media_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to modify this trip's media.")
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
                if collection is None or collection.deleted_at is not None:
                    return Failure(MediaCollectionNotFoundError(str(trip_id)))

                collection.update_caption(media_id, command.caption)
                item = collection._find_item(media_id)

                await self._repository.save(collection)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to update caption.", cause=exc))

        await self._publish(collection.pop_events(), context="update_caption")
        return Success(MediaItemSummary.from_entity(item))  # type: ignore[arg-type]

    async def delete_media(self, command: DeleteMediaCommand) -> DeleteMediaResult:
        """Soft delete a media item."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            media_id = MediaId.from_str(command.media_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to delete this media.")
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
                if collection is None or collection.deleted_at is not None:
                    return Failure(MediaCollectionNotFoundError(str(trip_id)))

                # Perform soft delete in the domain
                collection.delete_media(media_id)

                await self._repository.save(collection)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to delete media.", cause=exc))

        await self._publish(collection.pop_events(), context="delete_media")
        return Success(None)

    async def attach_to_activity(
        self, command: AttachMediaToActivityCommand
    ) -> AttachMediaToActivityResult:
        """Link a media item to an activity."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            media_id = MediaId.from_str(command.media_id)
            activity_id = ActivityId.from_str(command.activity_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to attach media for this trip.")
                    )

                # Verify activity exists
                itinerary = await self._itinerary_repository.find_by_trip_id(trip_id)
                activity_exists = False
                if itinerary is not None and not itinerary.is_deleted:
                    for day in itinerary.days:
                        for item in day.items:
                            if str(item.entity_id) == str(activity_id):
                                activity_exists = True
                                break

                if not activity_exists:
                    return Failure(
                        ValidationError(
                            f"Activity '{activity_id}' does not exist on this trip's itinerary.",
                            field="activity_id",
                        )
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
                if collection is None or collection.deleted_at is not None:
                    return Failure(MediaCollectionNotFoundError(str(trip_id)))

                collection.attach_to_activity(media_id, activity_id)
                item = collection._find_item(media_id)

                await self._repository.save(collection)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to attach media to activity.", cause=exc))

        await self._publish(collection.pop_events(), context="attach_to_activity")
        return Success(MediaItemSummary.from_entity(item))  # type: ignore[arg-type]

    async def attach_to_expense(
        self, command: AttachMediaToExpenseCommand
    ) -> AttachMediaToExpenseResult:
        """Link a media item to an expense."""
        try:
            trip_id = TripId.from_str(command.trip_id)
            media_id = MediaId.from_str(command.media_id)
            expense_id = ExpenseId.from_str(command.expense_id)
            requester_id = UserId.from_str(command.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to attach media for this trip.")
                    )

                # Verify expense exists
                budget = await self._budget_repository.find_by_trip_id(trip_id)
                expense_exists = False
                if budget is not None and not budget.is_deleted:
                    for exp in budget.expenses:
                        if str(exp.entity_id) == str(expense_id):
                            expense_exists = True
                            break

                if not expense_exists:
                    return Failure(
                        ValidationError(
                            f"Expense '{expense_id}' does not exist on this trip's budget.",
                            field="expense_id",
                        )
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
                if collection is None or collection.deleted_at is not None:
                    return Failure(MediaCollectionNotFoundError(str(trip_id)))

                collection.attach_to_expense(media_id, expense_id)
                item = collection._find_item(media_id)

                await self._repository.save(collection)
                await self._uow.commit()
        except TravixError as exc:
            return Failure(exc)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to attach media to expense.", cause=exc))

        await self._publish(collection.pop_events(), context="attach_to_expense")
        return Success(MediaItemSummary.from_entity(item))  # type: ignore[arg-type]

    # ------------------------------------------------------------------ #
    # Queries                                                              #
    # ------------------------------------------------------------------ #

    async def get_media(self, query: GetMediaQuery) -> GetMediaResult:
        """Get a single media item summary by media ID."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            media_id = MediaId.from_str(query.media_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(ForbiddenError("You do not have permission to view this media."))

                collection = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collection.", cause=exc))

        if collection is None or collection.deleted_at is not None:
            return Failure(MediaCollectionNotFoundError(str(trip_id)))

        item = collection._find_item(media_id)
        if item is None or item.status == MediaStatus.DELETED:
            return Failure(MediaItemNotFoundError(str(media_id)))

        return Success(MediaItemSummary.from_entity(item))

    async def list_media(self, query: ListMediaQuery) -> ListMediaResult:
        """List media items in the collection with cursor-based pagination."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to view media for this trip.")
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collection.", cause=exc))

        if collection is None or collection.deleted_at is not None:
            return Failure(MediaCollectionNotFoundError(str(trip_id)))

        # Filter only active (non-deleted) items
        active_items = [item for item in collection.items if item.status != MediaStatus.DELETED]
        active_items = sorted(
            active_items, key=lambda item: (item.created_at, str(item.entity_id)), reverse=True
        )

        # Pagination logic (keyset pagination on created_at and ID)
        after_id: str | None = None
        if query.cursor is not None:
            try:
                after_id = decode_cursor(query.cursor)
            except Exception:
                return Failure(
                    ValidationError(
                        "Invalid pagination cursor.", field="cursor", value=query.cursor
                    )
                )

        if after_id is not None:
            cursor_item = next(
                (item for item in active_items if str(item.entity_id) == after_id), None
            )
            if cursor_item is not None:
                active_items = [
                    item
                    for item in active_items
                    if (item.created_at, str(item.entity_id))
                    < (cursor_item.created_at, str(cursor_item.entity_id))
                ]

        has_more = len(active_items) > query.limit
        if has_more:
            active_items = active_items[: query.limit]

        next_cursor: str | None = None
        if has_more and active_items:
            next_cursor = encode_cursor(str(active_items[-1].entity_id))

        return Success(
            MediaListPage(
                items=tuple(MediaItemSummary.from_entity(item) for item in active_items),
                next_cursor=next_cursor,
                has_more=has_more,
                limit=query.limit,
            )
        )

    async def get_media_by_activity(
        self, query: GetMediaByActivityQuery
    ) -> GetMediaByActivityResult:
        """Retrieve all non-deleted media items attached to an activity."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            activity_id = ActivityId.from_str(query.activity_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to view media for this trip.")
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collection.", cause=exc))

        if collection is None or collection.deleted_at is not None:
            return Failure(MediaCollectionNotFoundError(str(trip_id)))

        attached = [
            item
            for item in collection.items
            if item.status != MediaStatus.DELETED
            and item.activity_id is not None
            and str(item.activity_id) == str(activity_id)
        ]
        attached = sorted(attached, key=lambda item: item.created_at, reverse=True)

        return Success([MediaItemSummary.from_entity(item) for item in attached])

    async def get_media_by_expense(self, query: GetMediaByExpenseQuery) -> GetMediaByExpenseResult:
        """Retrieve all non-deleted media items attached to an expense."""
        try:
            trip_id = TripId.from_str(query.trip_id)
            expense_id = ExpenseId.from_str(query.expense_id)
            requester_id = UserId.from_str(query.requester_id)
        except (ValueError, TravixError) as exc:
            return Failure(ValidationError(str(exc)))

        try:
            async with self._uow:
                session = self._uow._session  # type: ignore[attr-defined]
                has_access = await self._check_access(trip_id, requester_id, session)
                if not has_access:
                    return Failure(
                        ForbiddenError("You do not have permission to view media for this trip.")
                    )

                collection = await self._repository.find_by_trip_id(trip_id)
        except Exception as exc:
            return Failure(InfrastructureError("Failed to load collection.", cause=exc))

        if collection is None or collection.deleted_at is not None:
            return Failure(MediaCollectionNotFoundError(str(trip_id)))

        attached = [
            item
            for item in collection.items
            if item.status != MediaStatus.DELETED
            and item.expense_id is not None
            and str(item.expense_id) == str(expense_id)
        ]
        attached = sorted(attached, key=lambda item: item.created_at, reverse=True)

        return Success([MediaItemSummary.from_entity(item) for item in attached])

    # ------------------------------------------------------------------ #
    # Event publication                                                    #
    # ------------------------------------------------------------------ #

    async def _publish(self, events: Sequence[DomainEvent], *, context: str) -> None:
        """Publish domain events safely."""
        if not events:
            return
        try:
            await self._event_publisher.publish(events)
        except Exception as exc:
            logger.error(
                "Event publication failed",
                extra={
                    "context": context,
                    "event_count": len(events),
                    "reason": str(exc),
                },
            )
