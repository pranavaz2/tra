"""Media infrastructure repositories package."""

from app.modules.travel.media.infrastructure.repositories.media_repository import (
    SQLAlchemyMediaCollectionRepository,
)

__all__ = ["SQLAlchemyMediaCollectionRepository"]
