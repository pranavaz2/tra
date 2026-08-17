"""Unit tests for TripMediaCollection aggregate root and MediaItem entity."""

from __future__ import annotations

import pytest

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.modules.travel.media.domain.enums.media_status import MediaStatus
from app.modules.travel.media.domain.enums.media_type import MediaType
from app.modules.travel.media.domain.errors import (
    CaptionLengthExceededError,
    DuplicateMediaIdError,
    MaxFileSizeExceededError,
    MediaCollectionAlreadyLockedError,
    MediaItemNotFoundError,
    MimeTypeNotSupportedError,
)
from app.modules.travel.media.domain.events.media_events import (
    MediaAttachedToActivity,
    MediaAttachedToExpense,
    MediaCaptionUpdated,
    MediaDeleted,
    MediaUploaded,
)
from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.shared.domain.errors import ValidationError


# ──────────────────────────────────────────────────────────────────────────── #
# Test helpers                                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_collection(
    owner_id: UserId | None = None,
) -> TripMediaCollection:
    """Create a minimal TripMediaCollection for testing."""
    oid = owner_id or UserId.generate()
    return TripMediaCollection.create(
        collection_id=MediaCollectionId.generate(),
        trip_id=TripId.generate(),
        owner_id=oid,
    )


def _make_metadata(
    mime_type: str = "image/jpeg",
    size_bytes: int = 5000,
) -> MediaMetadata:
    return MediaMetadata(
        mime_type=mime_type,
        size_bytes=size_bytes,
        file_name="vacation.jpg",
        width=1200,
        height=800,
    )


# ──────────────────────────────────────────────────────────────────────────── #
# Creation & Defaults                                                             #
# ──────────────────────────────────────────────────────────────────────────── #


def test_collection_creation_defaults() -> None:
    """TripMediaCollection initializes with zero items and version 1."""
    trip_id = TripId.generate()
    owner_id = UserId.generate()
    cid = MediaCollectionId.generate()

    col = TripMediaCollection.create(
        collection_id=cid,
        trip_id=trip_id,
        owner_id=owner_id,
    )

    assert col.collection_id == cid
    assert col.trip_id == trip_id
    assert col.owner_id == owner_id
    assert len(col.items) == 0
    assert col.version == 1
    assert col.deleted_at is None
    assert len(col.pop_events()) == 0


# ──────────────────────────────────────────────────────────────────────────── #
# Upload Media Invariants                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


def test_upload_media_success() -> None:
    """upload_media adds item and emits MediaUploaded event."""
    col = _make_collection()
    mid = MediaId.generate()
    url = MediaUrl("https://storage.travix.ai/trips/media/vacation.jpg")
    meta = _make_metadata()
    uploader = UserId.generate()

    item = col.upload_media(
        media_id=mid,
        url=url,
        media_type=MediaType.PHOTO,
        metadata=meta,
        uploaded_by=uploader,
    )

    assert len(col.items) == 1
    assert item.entity_id == mid
    assert item.url == url
    assert item.media_type == MediaType.PHOTO
    assert item.status == MediaStatus.AVAILABLE
    assert item.uploaded_by == uploader
    assert item.caption is None
    assert item.activity_id is None
    assert item.expense_id is None

    events = col.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], MediaUploaded)
    assert events[0].media_id == str(mid)
    assert events[0].url == str(url)


def test_upload_media_requires_https() -> None:
    """Only HTTPS schemes are accepted in MediaUrl."""
    with pytest.raises(ValidationError, match="HTTPS"):
        MediaUrl("http://storage.travix.ai/vacation.jpg")

    with pytest.raises(ValidationError, match="HTTPS"):
        MediaUrl("ftp://storage/vacation.jpg")


def test_upload_media_rejects_unsupported_mime_type() -> None:
    """Unsupported MIME type raises MimeTypeNotSupportedError."""
    col = _make_collection()
    mid = MediaId.generate()
    url = MediaUrl("https://storage.travix.ai/file.exe")
    meta = _make_metadata(mime_type="application/x-msdownload")

    with pytest.raises(MimeTypeNotSupportedError):
        col.upload_media(
            media_id=mid,
            url=url,
            media_type=MediaType.NOTE,
            metadata=meta,
            uploaded_by=UserId.generate(),
        )


def test_upload_media_rejects_exceeded_file_size() -> None:
    """Large file size raises MaxFileSizeExceededError."""
    col = _make_collection()
    mid = MediaId.generate()
    url = MediaUrl("https://storage.travix.ai/movie.mp4")
    meta = _make_metadata(size_bytes=10000)

    with pytest.raises(MaxFileSizeExceededError):
        col.upload_media(
            media_id=mid,
            url=url,
            media_type=MediaType.VIDEO,
            metadata=meta,
            uploaded_by=UserId.generate(),
            max_file_size=5000,  # limit to 5000 bytes
        )


def test_upload_media_rejects_duplicate_id() -> None:
    """Uploading a media item with duplicate ID raises DuplicateMediaIdError."""
    col = _make_collection()
    mid = MediaId.generate()
    url = MediaUrl("https://storage.travix.ai/file1.jpg")
    meta = _make_metadata()
    uploader = UserId.generate()

    col.upload_media(
        media_id=mid,
        url=url,
        media_type=MediaType.PHOTO,
        metadata=meta,
        uploaded_by=uploader,
    )

    with pytest.raises(DuplicateMediaIdError):
        col.upload_media(
            media_id=mid,
            url=MediaUrl("https://storage.travix.ai/file2.jpg"),
            media_type=MediaType.PHOTO,
            metadata=meta,
            uploaded_by=uploader,
        )


# ──────────────────────────────────────────────────────────────────────────── #
# Captions & Lengths                                                             #
# ──────────────────────────────────────────────────────────────────────────── #


def test_update_caption_success() -> None:
    """OWNER can update caption, stripping whitespaces."""
    col = _make_collection()
    mid = MediaId.generate()
    col.upload_media(
        media_id=mid,
        url=MediaUrl("https://storage.travix.ai/file.jpg"),
        media_type=MediaType.PHOTO,
        metadata=_make_metadata(),
        uploaded_by=UserId.generate(),
    )
    col.pop_events()

    col.update_caption(mid, "   Fun day at the beach!   ")
    item = col._find_item(mid)
    assert item is not None
    assert item.caption == "Fun day at the beach!"

    events = col.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], MediaCaptionUpdated)
    assert events[0].media_id == str(mid)
    assert events[0].caption == "Fun day at the beach!"


def test_update_caption_too_long() -> None:
    """Caption longer than 500 chars raises CaptionLengthExceededError."""
    col = _make_collection()
    mid = MediaId.generate()
    col.upload_media(
        media_id=mid,
        url=MediaUrl("https://storage.travix.ai/file.jpg"),
        media_type=MediaType.PHOTO,
        metadata=_make_metadata(),
        uploaded_by=UserId.generate(),
    )

    long_caption = "A" * 501
    with pytest.raises(CaptionLengthExceededError):
        col.update_caption(mid, long_caption)


# ──────────────────────────────────────────────────────────────────────────── #
# Attachments                                                                     #
# ──────────────────────────────────────────────────────────────────────────── #


def test_attach_media_to_activity() -> None:
    """Linking to activity updates item property and emits domain event."""
    col = _make_collection()
    mid = MediaId.generate()
    col.upload_media(
        media_id=mid,
        url=MediaUrl("https://storage.travix.ai/file.jpg"),
        media_type=MediaType.PHOTO,
        metadata=_make_metadata(),
        uploaded_by=UserId.generate(),
    )
    col.pop_events()

    aid = ActivityId.generate()
    col.attach_to_activity(mid, aid)

    item = col._find_item(mid)
    assert item is not None
    assert item.activity_id == aid

    events = col.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], MediaAttachedToActivity)
    assert events[0].media_id == str(mid)
    assert events[0].activity_id == str(aid)


def test_attach_media_to_expense() -> None:
    """Linking to expense updates item property and emits domain event."""
    col = _make_collection()
    mid = MediaId.generate()
    col.upload_media(
        media_id=mid,
        url=MediaUrl("https://storage.travix.ai/file.jpg"),
        media_type=MediaType.PHOTO,
        metadata=_make_metadata(),
        uploaded_by=UserId.generate(),
    )
    col.pop_events()

    eid = ExpenseId.generate()
    col.attach_to_expense(mid, eid)

    item = col._find_item(mid)
    assert item is not None
    assert item.expense_id == eid

    events = col.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], MediaAttachedToExpense)
    assert events[0].media_id == str(mid)
    assert events[0].expense_id == str(eid)


# ──────────────────────────────────────────────────────────────────────────── #
# Soft Delete / Locks                                                             #
# ──────────────────────────────────────────────────────────────────────────── #


def test_delete_media_soft_deletes_item() -> None:
    """Soft delete sets item status to DELETED and emits MediaDeleted event."""
    col = _make_collection()
    mid = MediaId.generate()
    col.upload_media(
        media_id=mid,
        url=MediaUrl("https://storage.travix.ai/file.jpg"),
        media_type=MediaType.PHOTO,
        metadata=_make_metadata(),
        uploaded_by=UserId.generate(),
    )
    col.pop_events()

    col.delete_media(mid)

    item = col._find_item(mid)
    assert item is not None
    assert item.status == MediaStatus.DELETED

    events = col.pop_events()
    assert len(events) == 1
    assert isinstance(events[0], MediaDeleted)
    assert events[0].media_id == str(mid)


def test_modify_deleted_media_item_raises() -> None:
    """Updating caption or attaching links raises on soft-deleted items."""
    col = _make_collection()
    mid = MediaId.generate()
    col.upload_media(
        media_id=mid,
        url=MediaUrl("https://storage.travix.ai/file.jpg"),
        media_type=MediaType.PHOTO,
        metadata=_make_metadata(),
        uploaded_by=UserId.generate(),
    )
    col.delete_media(mid)

    with pytest.raises(MediaItemNotFoundError):
        col.update_caption(mid, "Caption text")

    with pytest.raises(MediaItemNotFoundError):
        col.attach_to_activity(mid, ActivityId.generate())

    with pytest.raises(MediaItemNotFoundError):
        col.attach_to_expense(mid, ExpenseId.generate())


def test_deleted_collection_locks_mutations() -> None:
    """All mutations fail if the TripMediaCollection aggregate is soft-deleted."""
    col = _make_collection()
    col.delete()

    with pytest.raises(MediaCollectionAlreadyLockedError):
        col.upload_media(
            media_id=MediaId.generate(),
            url=MediaUrl("https://storage.travix.ai/file.jpg"),
            media_type=MediaType.PHOTO,
            metadata=_make_metadata(),
            uploaded_by=UserId.generate(),
        )

    with pytest.raises(MediaCollectionAlreadyLockedError):
        col.update_caption(MediaId.generate(), "Text")

    with pytest.raises(MediaCollectionAlreadyLockedError):
        col.delete_media(MediaId.generate())
