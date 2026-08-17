"""Unit tests for MediaService using in-memory test doubles."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.budget.domain.entities.expense import Expense
from app.modules.travel.budget.domain.entities.trip_budget import TripBudget
from app.modules.travel.budget.domain.enums.expense_type import ExpenseType
from app.modules.travel.budget.domain.value_objects.budget_id import BudgetId
from app.modules.travel.budget.domain.value_objects.category_id import CategoryId
from app.modules.travel.budget.domain.value_objects.currency_code import CurrencyCode
from app.modules.travel.budget.domain.value_objects.expense_id import ExpenseId
from app.modules.travel.budget.domain.value_objects.money import Money
from app.modules.travel.itinerary.domain.entities.day import ItineraryDay
from app.modules.travel.itinerary.domain.entities.item import ItineraryItem
from app.modules.travel.itinerary.domain.entities.itinerary import Itinerary
from app.modules.travel.itinerary.domain.value_objects.day_id import ItineraryDayId
from app.modules.travel.itinerary.domain.value_objects.item_id import ItineraryItemId
from app.modules.travel.itinerary.domain.value_objects.item_title import ItemTitle
from app.modules.travel.itinerary.domain.value_objects.item_type import ItineraryItemType
from app.modules.travel.itinerary.domain.value_objects.itinerary_id import ItineraryId
from app.modules.travel.media.application.commands import (
    AttachMediaToActivityCommand,
    AttachMediaToExpenseCommand,
    DeleteMediaCommand,
    UpdateCaptionCommand,
    UploadMediaCommand,
)
from app.modules.travel.media.application.dtos import (
    MediaItemSummary,
    MediaListPage,
)
from app.modules.travel.media.application.media_service import MediaService
from app.modules.travel.media.application.queries import (
    GetMediaByActivityQuery,
    GetMediaByExpenseQuery,
    GetMediaQuery,
    ListMediaQuery,
)
from app.modules.travel.media.domain.entities.media_item import MediaItem
from app.modules.travel.media.domain.entities.trip_media_collection import (
    TripMediaCollection,
)
from app.modules.travel.media.domain.enums.media_status import MediaStatus
from app.modules.travel.media.domain.enums.media_type import MediaType
from app.modules.travel.media.domain.errors import (
    MaxFileSizeExceededError,
    MediaCollectionNotFoundError,
    MediaItemNotFoundError,
)
from app.modules.travel.media.domain.value_objects.activity_id import ActivityId
from app.modules.travel.media.domain.value_objects.media_collection_id import (
    MediaCollectionId,
)
from app.modules.travel.media.domain.value_objects.media_id import MediaId
from app.modules.travel.media.domain.value_objects.media_metadata import MediaMetadata
from app.modules.travel.media.domain.value_objects.media_url import MediaUrl
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.shared.domain.errors import ForbiddenError, ValidationError
from app.shared.domain.events import DomainEvent
from app.shared.domain.result import Failure, Success
from app.shared.infrastructure.clock import FixedClock

# ──────────────────────────────────────────────────────────────────────────── #
# Constants                                                                       #
# ──────────────────────────────────────────────────────────────────────────── #

FIXED_TIME = datetime(2026, 7, 16, 12, 0, 0, tzinfo=UTC)
FIXED_OWNER_UUID = UUID("da2c388a-2114-41d6-848e-6701bbabefd4")
FIXED_TRIP_UUID = UUID("b1836585-780c-40ef-8e8a-02d9a7442342")
FIXED_COLL_UUID = UUID("e819bcf8-87b4-4b55-8736-f3316dbcd3bf")
FIXED_MEDIA_UUID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


# ──────────────────────────────────────────────────────────────────────────── #
# Test Doubles                                                                    #
# ──────────────────────────────────────────────────────────────────────────── #


class InMemoryMediaCollectionRepository:
    """In-memory IMediaCollectionRepository."""

    def __init__(self) -> None:
        self._store: dict[UUID, TripMediaCollection] = {}

    async def find_by_id(
        self, collection_id: MediaCollectionId
    ) -> TripMediaCollection | None:
        return self._store.get(collection_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> TripMediaCollection | None:
        return next(
            (c for c in self._store.values() if c.trip_id == trip_id and not c.deleted_at),
            None,
        )

    async def save(self, collection: TripMediaCollection) -> None:
        self._store[collection.collection_id.value] = collection

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        return any(
            c.trip_id == trip_id and not c.deleted_at for c in self._store.values()
        )


class InMemoryTripRepository:
    """In-memory ITripRepository."""

    def __init__(self) -> None:
        self._store: dict[UUID, Trip] = {}

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        return self._store.get(trip_id.value)

    async def save(self, trip: Trip) -> None:
        self._store[trip.trip_id.value] = trip

    async def exists(self, trip_id: TripId) -> bool:
        t = self._store.get(trip_id.value)
        return t is not None and not t.is_deleted

    async def delete(self, trip_id: TripId) -> None:
        self._store.pop(trip_id.value, None)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: Any = None,
        status_filter: Any = None,
    ) -> list[Trip]:
        return list(self._store.values())[:limit]

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        return list(self._store.values())

    async def exists_with_title(self, owner_id: UserId, title: TripTitle) -> bool:
        return False


class InMemoryItineraryRepository:
    """In-memory IItineraryRepository."""

    def __init__(self) -> None:
        self._store: dict[UUID, Itinerary] = {}

    async def find_by_id(self, itinerary_id: ItineraryId) -> Itinerary | None:
        return self._store.get(itinerary_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> Itinerary | None:
        return next(
            (i for i in self._store.values() if i.trip_id == trip_id and not i.deleted_at),
            None,
        )

    async def save(self, itinerary: Itinerary) -> None:
        self._store[itinerary.itinerary_id.value] = itinerary

    async def exists(self, itinerary_id: ItineraryId) -> bool:
        i = self._store.get(itinerary_id.value)
        return i is not None and not i.deleted_at

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        return any(
            i.trip_id == trip_id and not i.deleted_at for i in self._store.values()
        )


class InMemoryBudgetRepository:
    """In-memory ITripBudgetRepository."""

    def __init__(self) -> None:
        self._store: dict[UUID, TripBudget] = {}

    async def find_by_id(self, budget_id: BudgetId) -> TripBudget | None:
        return self._store.get(budget_id.value)

    async def find_by_trip_id(self, trip_id: TripId) -> TripBudget | None:
        return next(
            (b for b in self._store.values() if b.trip_id == trip_id and not b.is_deleted),
            None,
        )

    async def save(self, budget: TripBudget) -> None:
        self._store[budget.budget_id.value] = budget

    async def exists(self, budget_id: BudgetId) -> bool:
        b = self._store.get(budget_id.value)
        return b is not None and not b.is_deleted

    async def exists_for_trip(self, trip_id: TripId) -> bool:
        return any(
            b.trip_id == trip_id and not b.is_deleted for b in self._store.values()
        )

    async def delete(self, budget_id: BudgetId) -> None:
        pass


class FakeStorageProvider:
    """Mock StorageProvider."""

    async def upload_file(
        self,
        file_content: bytes,
        destination_path: str,
        mime_type: str,
    ) -> str:
        return f"https://storage.travix.ai/{destination_path}"

    async def delete_file(self, file_url: str) -> None:
        pass


class FakeThumbnailGenerator:
    async def generate_thumbnail(
        self,
        image_content: bytes,
        width: int,
        height: int,
        mime_type: str,
    ) -> bytes:
        return b"thumbnail_bytes"


class FakeVirusScanner:
    """VirusScanner test double. Supports scanning and mock infection toggle."""

    def __init__(self) -> None:
        self.is_infected = False

    async def scan_file(self, file_content: bytes) -> bool:
        return not self.is_infected


class FakeMetadataExtractor:
    """Extractor test double. Customizable attributes."""

    def __init__(self) -> None:
        self.width = 1920
        self.height = 1080

    async def extract_metadata(
        self,
        file_content: bytes,
        mime_type: str,
    ) -> dict[str, Any]:
        return {"width": self.width, "height": self.height}


class InMemoryEventPublisher:
    def __init__(self) -> None:
        self.published: list[DomainEvent] = []

    async def publish(self, events: Sequence[DomainEvent]) -> None:
        self.published.extend(events)


class FakeSession:
    """Mock database session to emulate check_access select calls."""

    async def execute(self, statement: Any) -> Any:
        class Result:
            def scalar(self) -> Any:
                return None  # default: not a collaborator in mock checks
        return Result()


class InMemoryUnitOfWork:
    def __init__(self) -> None:
        self._session = FakeSession()

    async def __aenter__(self) -> InMemoryUnitOfWork:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


class FixedUUIDProvider:
    def __init__(self, value: UUID) -> None:
        self._value = value

    def generate(self) -> UUID:
        return self._value


# ──────────────────────────────────────────────────────────────────────────── #
# Service Composers                                                               #
# ──────────────────────────────────────────────────────────────────────────── #


def _make_service(
    fixed_uuid: UUID = FIXED_MEDIA_UUID,
) -> tuple[
    MediaService,
    InMemoryMediaCollectionRepository,
    InMemoryTripRepository,
    InMemoryItineraryRepository,
    InMemoryBudgetRepository,
    FakeVirusScanner,
    InMemoryEventPublisher,
]:
    repo = InMemoryMediaCollectionRepository()
    trip_repo = InMemoryTripRepository()
    itinerary_repo = InMemoryItineraryRepository()
    budget_repo = InMemoryBudgetRepository()
    storage = FakeStorageProvider()
    thumb = FakeThumbnailGenerator()
    scanner = FakeVirusScanner()
    extractor = FakeMetadataExtractor()
    uow = InMemoryUnitOfWork()
    pub = InMemoryEventPublisher()
    uuid_prov = FixedUUIDProvider(fixed_uuid)
    clock = FixedClock(FIXED_TIME)

    service = MediaService(
        repository=repo,
        trip_repository=trip_repo,
        itinerary_repository=itinerary_repo,
        budget_repository=budget_repo,
        storage_provider=storage,
        thumbnail_generator=thumb,
        virus_scanner=scanner,
        metadata_extractor=extractor,
        unit_of_work=uow,
        event_publisher=pub,
        uuid_provider=uuid_prov,
        clock=clock,
    )
    return service, repo, trip_repo, itinerary_repo, budget_repo, scanner, pub


def _make_trip(
    owner_id: UserId,
) -> Trip:
    return Trip.create(
        trip_id=TripId(value=FIXED_TRIP_UUID),
        owner_id=owner_id,
        title=TripTitle("My vacation"),
        date_range=TripDateRange(
            departure_date=date(2026, 8, 1),
            return_date=date(2026, 8, 10),
        ),
        privacy=TripPrivacy.PRIVATE,
    )


# ──────────────────────────────────────────────────────────────────────────── #
# upload_media                                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_upload_media_success() -> None:
    """Orchestrates metadata extraction, uploads to storage, and persists collection."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, _, _, _, pub = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="vacation.png",
        file_content=b"file_bytes",
        mime_type="image/png",
        uploaded_by=str(FIXED_OWNER_UUID),
    )

    result = await service.upload_media(cmd)

    assert isinstance(result, Success)
    summary: MediaItemSummary = result.value
    assert summary.file_name == "vacation.png"
    assert summary.mime_type == "image/png"
    assert summary.url == f"https://storage.travix.ai/trips/{FIXED_TRIP_UUID}/media/{FIXED_MEDIA_UUID}_vacation.png"
    assert summary.width == 1920
    assert summary.height == 1080

    # Collection bootstrapped
    collection = await repo.find_by_trip_id(TripId(value=FIXED_TRIP_UUID))
    assert collection is not None
    assert len(collection.items) == 1
    assert len(pub.published) == 1


@pytest.mark.asyncio
async def test_upload_media_virus_infected_rejected() -> None:
    """Returns ValidationError when virus scanner detects infected files."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, _, trip_repo, _, _, scanner, _ = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    scanner.is_infected = True

    cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="harmful.jpg",
        file_content=b"malicious_bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )

    result = await service.upload_media(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValidationError)
    assert "Virus detected" in result.error.message


@pytest.mark.asyncio
async def test_upload_media_not_owner_forbidden() -> None:
    """Requester who doesn't own trip and isn't collaborator gets ForbiddenError."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, _, trip_repo, _, _, _, _ = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    non_owner = UserId.generate()
    cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="vacation.png",
        file_content=b"file_bytes",
        mime_type="image/png",
        uploaded_by=str(non_owner),
    )

    result = await service.upload_media(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ForbiddenError)


# ──────────────────────────────────────────────────────────────────────────── #
# update_caption                                                                 #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_update_caption_success() -> None:
    """Updates caption successfully and publishes event."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, _, _, _, pub = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    # upload first
    upload_cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="pic.jpg",
        file_content=b"bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )
    await service.upload_media(upload_cmd)

    cmd = UpdateCaptionCommand(
        trip_id=str(FIXED_TRIP_UUID),
        media_id=str(FIXED_MEDIA_UUID),
        caption="A beautiful sunset",
        requester_id=str(FIXED_OWNER_UUID),
    )

    result = await service.update_caption(cmd)
    assert isinstance(result, Success)
    assert result.value.caption == "A beautiful sunset"


# ──────────────────────────────────────────────────────────────────────────── #
# delete_media                                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_delete_media_success() -> None:
    """Soft deletes media reference by changing state to deleted."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, _, _, _, pub = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    upload_cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="pic.jpg",
        file_content=b"bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )
    await service.upload_media(upload_cmd)

    cmd = DeleteMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        media_id=str(FIXED_MEDIA_UUID),
        requester_id=str(FIXED_OWNER_UUID),
    )

    result = await service.delete_media(cmd)
    assert isinstance(result, Success)

    collection = await repo.find_by_trip_id(TripId(value=FIXED_TRIP_UUID))
    assert collection is not None
    item = collection._find_item(MediaId(value=FIXED_MEDIA_UUID))
    assert item is not None
    assert item.status == MediaStatus.DELETED


# ──────────────────────────────────────────────────────────────────────────── #
# attach_to_activity / expense                                                   #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_attach_media_to_activity_success() -> None:
    """Links media item to itinerary activity if the activity is present."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, itinerary_repo, _, _, pub = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    # Save mock itinerary with day and activity
    itin_id = ItineraryId.generate()
    itinerary = Itinerary.create(itinerary_id=itin_id, trip_id=TripId(value=FIXED_TRIP_UUID))
    day_id = ItineraryDayId.generate()
    day = ItineraryDay(entity_id=day_id, itinerary_id=itin_id, day_number=1, title="Day 1")
    act_uuid = UUID("11111111-2222-3333-4444-555555555555")
    activity = ItineraryItem(
        entity_id=ItineraryItemId(value=act_uuid),
        day_id=day_id,
        title=ItemTitle("Eiffel Tower visit"),
        item_type=ItineraryItemType.ACTIVITY,
    )
    day.items.append(activity)
    itinerary.days.append(day)
    await itinerary_repo.save(itinerary)

    upload_cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="pic.jpg",
        file_content=b"bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )
    await service.upload_media(upload_cmd)

    cmd = AttachMediaToActivityCommand(
        trip_id=str(FIXED_TRIP_UUID),
        media_id=str(FIXED_MEDIA_UUID),
        activity_id=str(act_uuid),
        requester_id=str(FIXED_OWNER_UUID),
    )

    result = await service.attach_to_activity(cmd)
    assert isinstance(result, Success)
    assert result.value.activity_id == str(act_uuid)


@pytest.mark.asyncio
async def test_attach_media_to_activity_missing_raises() -> None:
    """Returns ValidationError when link target activity is absent on trip itinerary."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, _, _, _, _ = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    upload_cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="pic.jpg",
        file_content=b"bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )
    await service.upload_media(upload_cmd)

    # Target absent activity ID
    missing_act = UUID("99999999-8888-7777-6666-555555555555")
    cmd = AttachMediaToActivityCommand(
        trip_id=str(FIXED_TRIP_UUID),
        media_id=str(FIXED_MEDIA_UUID),
        activity_id=str(missing_act),
        requester_id=str(FIXED_OWNER_UUID),
    )

    result = await service.attach_to_activity(cmd)
    assert isinstance(result, Failure)
    assert isinstance(result.error, ValidationError)


@pytest.mark.asyncio
async def test_attach_media_to_expense_success() -> None:
    """Links media item to expense successfully if the expense exists."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, _, budget_repo, _, pub = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    # Save mock budget with expense
    bid = BudgetId.generate()
    budget = TripBudget.create(
        budget_id=bid,
        trip_id=TripId(value=FIXED_TRIP_UUID),
        owner_id=owner_id,
        limit=Money(amount=Decimal("1000.00"), currency=CurrencyCode("USD")),
    )
    exp_uuid = UUID("22222222-3333-4444-5555-666666666666")
    expense = Expense(
        entity_id=ExpenseId(value=exp_uuid),
        title="French Lunch",
        amount=Money(amount=Decimal("50.00"), currency=CurrencyCode("USD")),
        category_id=CategoryId.generate(),
        expense_type=ExpenseType.RESTAURANT,
        expense_date=date(2026, 8, 2),
    )
    budget.expenses.append(expense)
    await budget_repo.save(budget)

    upload_cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="pic.jpg",
        file_content=b"bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )
    await service.upload_media(upload_cmd)

    cmd = AttachMediaToExpenseCommand(
        trip_id=str(FIXED_TRIP_UUID),
        media_id=str(FIXED_MEDIA_UUID),
        expense_id=str(exp_uuid),
        requester_id=str(FIXED_OWNER_UUID),
    )

    result = await service.attach_to_expense(cmd)
    assert isinstance(result, Success)
    assert result.value.expense_id == str(exp_uuid)


# ──────────────────────────────────────────────────────────────────────────── #
# Queries                                                                         #
# ──────────────────────────────────────────────────────────────────────────── #


@pytest.mark.asyncio
async def test_get_media_queries() -> None:
    """Queries return details and support list cursor pagination."""
    owner_id = UserId(value=FIXED_OWNER_UUID)
    service, repo, trip_repo, _, _, _, _ = _make_service()

    trip = _make_trip(owner_id=owner_id)
    await trip_repo.save(trip)

    upload_cmd = UploadMediaCommand(
        trip_id=str(FIXED_TRIP_UUID),
        file_name="pic.jpg",
        file_content=b"bytes",
        mime_type="image/jpeg",
        uploaded_by=str(FIXED_OWNER_UUID),
    )
    await service.upload_media(upload_cmd)

    # 1. Get media
    get_res = await service.get_media(
        GetMediaQuery(
            trip_id=str(FIXED_TRIP_UUID),
            media_id=str(FIXED_MEDIA_UUID),
            requester_id=str(FIXED_OWNER_UUID),
        )
    )
    assert isinstance(get_res, Success)
    assert get_res.value.media_id == str(FIXED_MEDIA_UUID)

    # 2. List media
    list_res = await service.list_media(
        ListMediaQuery(
            trip_id=str(FIXED_TRIP_UUID),
            requester_id=str(FIXED_OWNER_UUID),
            limit=10,
        )
    )
    assert isinstance(list_res, Success)
    page: MediaListPage = list_res.value
    assert len(page.items) == 1
    assert page.has_more is False
