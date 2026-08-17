"""
SQLAlchemyTripRepository — infrastructure implementation of ITripRepository.

Responsibilities:
  - Map between Trip domain entities and TripModel ORM rows.
  - Execute async SQLAlchemy queries against the trips table.
  - Apply soft-delete filtering on every list/existence query.
  - Enforce optimistic locking via SQLAlchemy's version_id_col mechanism.

What this class does NOT do:
  - Commit or roll back transactions (caller's responsibility).
  - Enforce business rules (domain entity's responsibility).
  - Construct or dispatch domain events.

Session contract:
  All methods call session.flush() to write to the current transaction without
  committing. The calling application layer (use case or FastAPI dependency)
  controls the commit boundary.

Optimistic locking notes:
  TripModel activates version_id_col. On every ORM UPDATE, SQLAlchemy issues:
      UPDATE trips SET ..., version = version + 1 WHERE id = ? AND version = ?
  If the WHERE clause matches zero rows (concurrent write), SQLAlchemy raises
  sqlalchemy.orm.exc.StaleDataError. This propagates to the application layer
  for handling (e.g., retry or surface a conflict error to the client).

  IMPORTANT: _apply_to_existing() intentionally does NOT copy trip.version to
  model.version. The ORM model's tracked version (loaded at find_by_id time) is
  what SQLAlchemy uses as the expected version in the WHERE clause. Copying the
  incremented domain version onto the tracked model would advance SQLAlchemy's
  expectation past the actual DB value, causing StaleDataError on every update.

Cursor pagination:
  find_by_owner() orders by (created_at DESC, id DESC) and uses a keyset filter
  expressed as:
      WHERE (created_at < cursor_trip.created_at)
         OR (created_at = cursor_trip.created_at AND id < cursor_trip.id)
  cursor_trip.created_at is resolved via a scalar subquery in the same database
  round-trip (no second query issued).

Mapper:
  _to_domain() reconstructs domain value objects from raw ORM column values.
  TripTitle.__post_init__ re-validates and re-strips, which is safe because DB
  data was validated on write. TripDateRange is reconstructed only when
  departure_date is non-NULL.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.query import exclude_deleted
from app.modules.identity.authentication.domain.value_objects.user_id import UserId
from app.modules.travel.trips.domain.entities.trip import Trip
from app.modules.travel.trips.domain.repositories.interfaces import ITripRepository
from app.modules.travel.trips.domain.value_objects.trip_date_range import TripDateRange
from app.modules.travel.trips.domain.value_objects.trip_id import TripId
from app.modules.travel.trips.domain.value_objects.trip_privacy import TripPrivacy
from app.modules.travel.trips.domain.value_objects.trip_status import TripStatus
from app.modules.travel.trips.domain.value_objects.trip_title import TripTitle
from app.modules.travel.trips.infrastructure.models.trip_model import TripModel


class SQLAlchemyTripRepository:
    """
    Async SQLAlchemy implementation of ITripRepository.

    Injected by FastAPI's dependency system. Holds a single AsyncSession
    for the lifetime of the HTTP request.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ---------------------------------------------------------------------- #
    # ITripRepository — reads                                                  #
    # ---------------------------------------------------------------------- #

    async def find_by_id(self, trip_id: TripId) -> Trip | None:
        """
        Return the Trip with the given ID, or None if not found.

        Uses the session identity map so repeated calls within the same
        request are free (no extra SQL). Soft-deleted trips ARE returned;
        callers decide how to handle them.
        """
        model = await self._session.get(TripModel, trip_id.value)
        if model is None:
            return None
        return self._to_domain(model)

    async def find_by_owner(
        self,
        owner_id: UserId,
        *,
        limit: int,
        after_id: TripId | None = None,
        status_filter: TripStatus | None = None,
    ) -> list[Trip]:
        """
        Return up to limit non-deleted trips owned by owner_id.

        Ordered newest-first by (created_at DESC, id DESC). Callers should
        request limit + 1 items to determine whether a next page exists, then
        strip the last item before returning to the client.

        Cursor (after_id):
          The ID of the last trip seen on the previous page. Resolved to
          created_at via a scalar subquery so keyset filtering works correctly
          without a separate database round-trip.

        Status filter:
          When provided, restricts results to trips in that status only.
        """
        stmt = (
            select(TripModel)
            .where(TripModel.owner_id == owner_id.value)
        )
        stmt = exclude_deleted(stmt, TripModel)

        if status_filter is not None:
            stmt = stmt.where(TripModel.status == status_filter.value)

        if after_id is not None:
            cursor_created_at = (
                select(TripModel.created_at)
                .where(TripModel.id == after_id.value)
                .scalar_subquery()
            )
            stmt = stmt.where(
                or_(
                    TripModel.created_at < cursor_created_at,
                    and_(
                        TripModel.created_at == cursor_created_at,
                        TripModel.id < after_id.value,
                    ),
                )
            )

        stmt = (
            stmt
            .order_by(TripModel.created_at.desc(), TripModel.id.desc())
            .limit(limit)
        )

        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars()]

    async def find_active_for_user(self, user_id: UserId) -> list[Trip]:
        """
        Return all non-deleted PLANNED or ACTIVE trips owned by user_id.

        Used for the "My Trips" home-screen widget. Ordered by departure_date
        ascending (soonest first) with NULL departure_dates sorted last.
        """
        stmt = (
            select(TripModel)
            .where(TripModel.owner_id == user_id.value)
            .where(
                TripModel.status.in_(
                    [TripStatus.PLANNED.value, TripStatus.ACTIVE.value]
                )
            )
        )
        stmt = exclude_deleted(stmt, TripModel)
        stmt = stmt.order_by(
            TripModel.departure_date.asc().nulls_last(),
            TripModel.created_at.asc(),
        )

        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars()]

    async def exists(self, trip_id: TripId) -> bool:
        """Return True if a non-deleted trip with this ID exists."""
        stmt = (
            select(TripModel.id)
            .where(TripModel.id == trip_id.value)
            .where(TripModel.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def exists_with_title(
        self,
        owner_id: UserId,
        title: TripTitle,
    ) -> bool:
        """
        Return True if owner_id already has a non-deleted trip whose title
        matches case-insensitively.

        Not a hard uniqueness constraint — used to warn users of duplicates
        before calling Trip.create().
        """
        stmt = (
            select(TripModel.id)
            .where(TripModel.owner_id == owner_id.value)
            .where(func.lower(TripModel.title) == func.lower(str(title)))
            .where(TripModel.deleted_at.is_(None))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ---------------------------------------------------------------------- #
    # ITripRepository — writes                                                 #
    # ---------------------------------------------------------------------- #

    async def save(self, trip: Trip) -> None:
        """
        Persist a new or updated trip within the current transaction.

        INSERT path (new trip):
          Creates a new TripModel, sets all fields from the domain entity, and
          calls session.add(). version is initialised to 1 regardless of the
          domain entity's version counter (DB and domain both start at 1).

        UPDATE path (existing trip):
          Retrieves the session-tracked TripModel via the identity map (no extra
          SQL if find_by_id was already called) and updates mutable fields via
          _apply_to_existing(). Does NOT copy trip.version to the model — see
          module docstring for why.

        Calls flush() to write to the database immediately without committing.

        Raises:
          sqlalchemy.orm.exc.StaleDataError: if concurrent update detected
            (version mismatch at UPDATE time).
        """
        existing = await self._session.get(TripModel, trip.entity_id.value)
        if existing is None:
            self._session.add(self._to_new_model(trip))
        else:
            self._apply_to_existing(trip, existing)
        await self._session.flush()

    async def delete(self, trip_id: TripId) -> None:
        """
        Hard-delete the trips row with the given ID.

        Intended for GDPR erasure and data-retention flows only. For
        user-initiated deletion, the application layer calls trip.delete()
        (soft delete) followed by save(trip).

        Silently succeeds if the row does not exist (idempotent).
        Calls flush() so the DELETE is visible to the current transaction.
        """
        model = await self._session.get(TripModel, trip_id.value)
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()

    # ---------------------------------------------------------------------- #
    # Private — ORM ↔ domain mappers                                          #
    # ---------------------------------------------------------------------- #

    def _to_domain(self, model: TripModel) -> Trip:
        """
        Reconstruct a Trip domain entity from a TripModel ORM row.

        TripDateRange is only created when departure_date is non-NULL. A NULL
        departure_date with a non-NULL return_date cannot exist in the database
        (enforced by ck_trips_return_requires_departure), so the simple NULL
        check on departure_date is sufficient.

        created_at and updated_at are passed through from the model so the
        domain entity's audit timestamps reflect the persisted values, not the
        in-memory construction time.
        """
        date_range: TripDateRange | None = None
        if model.departure_date is not None:
            date_range = TripDateRange(
                departure_date=model.departure_date,
                return_date=model.return_date,
                is_flexible=model.is_date_flexible,
            )

        return Trip(
            entity_id=TripId(value=model.id),
            owner_id=UserId(value=model.owner_id),
            title=TripTitle(value=model.title),
            status=TripStatus(model.status),
            privacy=TripPrivacy(model.privacy),
            date_range=date_range,
            version=model.version,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _to_new_model(self, trip: Trip) -> TripModel:
        """
        Create a TripModel instance for a first-time INSERT.

        Sets all business columns and audit timestamps from the domain entity.
        version is always initialised to 1 because SQLAlchemy's version tracking
        begins from the DB-side value regardless of the domain entity's counter.
        deleted_at is always None for a newly created trip.
        """
        dr = trip.date_range
        return TripModel(
            id=trip.entity_id.value,
            owner_id=trip.owner_id.value,
            title=str(trip.title),
            status=trip.status.value,
            privacy=trip.privacy.value,
            departure_date=dr.departure_date if dr is not None else None,
            return_date=dr.return_date if dr is not None else None,
            is_date_flexible=dr.is_flexible if dr is not None else False,
            version=1,
            created_at=trip.created_at,
            updated_at=trip.updated_at,
            deleted_at=None,
        )

    def _apply_to_existing(self, trip: Trip, model: TripModel) -> None:
        """
        Write mutable domain fields onto an already-tracked TripModel.

        Intentionally excluded fields:
          id          — primary key, immutable.
          owner_id    — ownership is immutable after creation.
          created_at  — set once on INSERT, immutable thereafter.
          version     — managed exclusively by SQLAlchemy's version_id_col;
                        see module docstring for why copying trip.version here
                        would break optimistic locking.

        Included: title, status, privacy, date range columns, deleted_at.
        deleted_at must be included so that Trip.delete() (soft delete) is
        persisted when the caller subsequently calls save(trip).
        """
        dr = trip.date_range
        model.title = str(trip.title)
        model.status = trip.status.value
        model.privacy = trip.privacy.value
        model.departure_date = dr.departure_date if dr is not None else None
        model.return_date = dr.return_date if dr is not None else None
        model.is_date_flexible = dr.is_flexible if dr is not None else False
        model.deleted_at = trip.deleted_at

