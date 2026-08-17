"""SQLAlchemy repository implementation for TripMediaCollection."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.query import exclude_deleted
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.media.domain.entities.media_item import MediaItem
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.modules.travel.media.domain.enums.media_status import MediaStatus
from app.modules.travel.media.domain.enums.media_type import MediaType
from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl
from app.modules.travel.media.infrastructure.models.media_model import (
    MediaItemModel,
    TripMediaCollectionModel,
)
from app.modules.travel.trips.domain.value_objects.trip_id import TripId


class SQLAlchemyMediaCollectionRepository:
    """SQLAlchemy implementation of IMediaCollectionRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def find_by_id(self, collection_id: MediaCollectionId) -> TripMediaCollection | None:
        """Find media collection by its primary ID."""
        stmt = select(TripMediaCollectionModel).where(
            TripMediaCollectionModel.id == collection_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_trip_id(self, trip_id: TripId) -> TripMediaCollection | None:
        """Find the latest active (non-deleted) media collection for a trip."""
        stmt = select(TripMediaCollectionModel).where(
            TripMediaCollectionModel.trip_id == trip_id.value
        )
        stmt = exclude_deleted(stmt, TripMediaCollectionModel)
        stmt = stmt.order_by(
            TripMediaCollectionModel.created_at.desc(),
            TripMediaCollectionModel.id.desc(),
        ).limit(1)

        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_domain(model)

    async def save(self, collection: TripMediaCollection) -> None:
        """Persist or update a TripMediaCollection aggregate."""
        stmt = select(TripMediaCollectionModel).where(
            TripMediaCollectionModel.id == collection.collection_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            model = self._to_new_model(collection)
            self._session.add(model)
        else:
            self._apply_to_existing(collection, model)

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        """Check if a media collection exists for the trip."""
        stmt = select(TripMediaCollectionModel.id).where(
            TripMediaCollectionModel.trip_id == trip_id.value
        )
        stmt = exclude_deleted(stmt, TripMediaCollectionModel)
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    # ------------------------------------------------------------------ #
    # Domain Mapping Helpers                                               #
    # ------------------------------------------------------------------ #

    def _to_domain(self, model: TripMediaCollectionModel) -> TripMediaCollection:
        """Convert ORM model to domain aggregate root."""
        items = [
            MediaItem(
                entity_id=MediaId(item.id),
                collection_id=MediaCollectionId(item.collection_id),
                url=MediaUrl(item.url),
                media_type=MediaType(item.media_type),
                status=MediaStatus(item.status),
                metadata=MediaMetadata.from_dict(item.metadata_json),
                caption=item.caption,
                uploaded_by=UserId(item.uploaded_by),
                activity_id=ActivityId(item.activity_id) if item.activity_id else None,
                expense_id=ExpenseId(item.expense_id) if item.expense_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in model.items
        ]

        collection = TripMediaCollection(
            entity_id=MediaCollectionId(model.id),
            trip_id=TripId(model.trip_id),
            owner_id=UserId(model.owner_id),
            items=items,
            version=model.version,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

        collection.pop_events()
        return collection

    def _to_new_model(self, collection: TripMediaCollection) -> TripMediaCollectionModel:
        """Map brand-new domain aggregate to SQLAlchemy ORM model."""
        model = TripMediaCollectionModel(
            id=collection.collection_id.value,
            trip_id=collection.trip_id.value,
            owner_id=collection.owner_id.value,
            version=collection.version,
            deleted_at=collection.deleted_at,
            created_at=collection.created_at,
            updated_at=collection.updated_at,
        )

        model.items = [
            MediaItemModel(
                id=item.entity_id.value,
                collection_id=model.id,
                url=str(item.url),
                media_type=item.media_type.value,
                status=item.status.value,
                metadata_json=item.metadata.to_dict(),
                caption=item.caption,
                uploaded_by=item.uploaded_by.value,
                activity_id=item.activity_id.value if item.activity_id else None,
                expense_id=item.expense_id.value if item.expense_id else None,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in collection.items
        ]

        return model

    def _apply_to_existing(
        self, collection: TripMediaCollection, model: TripMediaCollectionModel
    ) -> None:
        """Merge modifications from domain aggregate to existing ORM model."""
        model.deleted_at = collection.deleted_at
        model.updated_at = collection.updated_at
        model.version = collection.version

        # Sync items (insert, update, delete-orphan)
        existing_items = {item.id: item for item in model.items}
        new_items = []
        for domain_item in collection.items:
            item_id = domain_item.entity_id.value
            if item_id in existing_items:
                item_model = existing_items[item_id]
                item_model.status = domain_item.status.value
                item_model.url = str(domain_item.url)
                item_model.caption = domain_item.caption
                item_model.metadata_json = domain_item.metadata.to_dict()
                item_model.activity_id = (
                    domain_item.activity_id.value if domain_item.activity_id else None
                )
                item_model.expense_id = (
                    domain_item.expense_id.value if domain_item.expense_id else None
                )
                item_model.updated_at = domain_item.updated_at
            else:
                item_model = MediaItemModel(
                    id=item_id,
                    collection_id=model.id,
                    url=str(domain_item.url),
                    media_type=domain_item.media_type.value,
                    status=domain_item.status.value,
                    metadata_json=domain_item.metadata.to_dict(),
                    caption=domain_item.caption,
                    uploaded_by=domain_item.uploaded_by.value,
                    activity_id=domain_item.activity_id.value if domain_item.activity_id else None,
                    expense_id=domain_item.expense_id.value if domain_item.expense_id else None,
                    created_at=domain_item.created_at,
                    updated_at=domain_item.updated_at,
                )
            new_items.append(item_model)
        model.items = new_items
