"""
Travix AI — Query Helpers

Reusable building blocks for constructing SQLAlchemy SELECT statements:

  - SortDirection       → enum of ASC / DESC
  - SortSpec            → a column + direction pair
  - apply_sort()        → add ORDER BY clauses to a statement
  - exclude_deleted()   → add WHERE deleted_at IS NULL
  - ClauseSpecification → Specification[E] subtype with ``to_clause()``
  - apply_specification → apply a ClauseSpecification to a statement
  - paginate()          → cursor-based SELECT with automatic next-cursor encoding

All functions accept and return ``Select[tuple[E]]`` from sqlalchemy so they
compose cleanly with feature repository query builders:

    stmt = (
        select(TripModel)
        .where(TripModel.owner_id == user_id)
    )
    stmt = exclude_deleted(stmt, TripModel)
    stmt = apply_sort(stmt, SortSpec(TripModel.created_at, SortDirection.DESC))

    items, next_cursor = await paginate(
        session,
        stmt,
        cursor=query_cursor,
        limit=20,
        cursor_column=TripModel.id,
    )

Soft-delete convention:
  ``exclude_deleted()`` is the canonical helper for filtering soft-deleted rows.
  Every feature repository list/search method MUST call it unless the method
  explicitly returns deleted records (e.g., an admin endpoint).

ClauseSpecification:
  A ``Specification[E]`` that can also translate itself into a SQLAlchemy
  WHERE clause. This is the bridge between the domain-layer Specification
  pattern (in-memory filtering) and the infrastructure-layer SQL generation.

  Both methods must agree on semantics:
    - ``is_satisfied_by(entity)`` filters Python objects in-memory.
    - ``to_clause()``            filters database rows via SQL.

  ClauseSpecification allows a query to be expressed once as a business rule
  and applied either in-memory (unit tests, small lists) or as SQL (production
  queries over large datasets).
"""

from __future__ import annotations

import enum
from abc import abstractmethod
from typing import Any, TypeVar

from sqlalchemy import Select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, decode_cursor, encode_cursor
from app.shared.domain.specification import Specification

E = TypeVar("E")


# ---------------------------------------------------------------------------
# Sort helpers
# ---------------------------------------------------------------------------


class SortDirection(str, enum.Enum):
    """SQL sort direction."""

    ASC = "asc"
    DESC = "desc"


class SortSpec:
    """
    A sort specification combining a column reference and a direction.

    Usage:
        sort = SortSpec(TripModel.created_at, SortDirection.DESC)
        stmt = apply_sort(stmt, sort)
    """

    def __init__(
        self,
        column: InstrumentedAttribute[Any],
        direction: SortDirection = SortDirection.ASC,
    ) -> None:
        self.column = column
        self.direction = direction

    def to_order_clause(self) -> Any:
        """Return the SQLAlchemy ORDER BY expression."""
        if self.direction == SortDirection.DESC:
            return desc(self.column)
        return asc(self.column)


def apply_sort(query: Select[Any], *sorts: SortSpec) -> Select[Any]:
    """
    Apply one or more SortSpec items to a SELECT statement.

    Sorts are applied left-to-right (primary sort first). An empty ``sorts``
    list returns the query unchanged.
    """
    for sort in sorts:
        query = query.order_by(sort.to_order_clause())
    return query


# ---------------------------------------------------------------------------
# Soft-delete filter
# ---------------------------------------------------------------------------


def exclude_deleted(query: Select[Any], model: type[Any]) -> Select[Any]:
    """
    Add a ``WHERE deleted_at IS NULL`` clause to exclude soft-deleted rows.

    Requires the model to use ``SoftDeleteMixin``. Call this on every list
    or search query to prevent deleted records from appearing in responses.

    Args:
        query: An existing SELECT statement.
        model: The ORM model class (must have a ``deleted_at`` column).

    Returns:
        The query with the soft-delete filter applied.

    Raises:
        AttributeError: If the model does not have a ``deleted_at`` column.
    """
    return query.where(model.deleted_at.is_(None))


# ---------------------------------------------------------------------------
# Specification-to-clause bridge
# ---------------------------------------------------------------------------


class ClauseSpecification(Specification[E]):
    """
    A Specification that can also translate into a SQLAlchemy WHERE clause.

    Subclass this when a business rule needs to apply both:
      1. In-memory (Python): via ``is_satisfied_by()``  — used in unit tests
         and small collection filtering.
      2. As SQL: via ``to_clause()``  — used in repository queries for
         efficient database-side filtering.

    Both methods must agree on semantics. Divergence is a bug.

    Usage:
        class ActiveTrip(ClauseSpecification[TripModel]):
            def is_satisfied_by(self, candidate: TripModel) -> bool:
                return candidate.deleted_at is None and candidate.status == "active"

            def to_clause(self) -> ColumnElement[bool]:
                return and_(
                    TripModel.deleted_at.is_(None),
                    TripModel.status == "active",
                )

        # In a repository:
        stmt = apply_specification(select(TripModel), ActiveTrip())
    """

    @abstractmethod
    def to_clause(self) -> ColumnElement[bool]:
        """Return a SQLAlchemy column element usable as a WHERE predicate."""
        ...


def apply_specification(
    query: Select[Any],
    spec: ClauseSpecification[Any],
) -> Select[Any]:
    """
    Apply a ClauseSpecification's WHERE clause to a SELECT statement.

    Args:
        query: An existing SELECT statement.
        spec:  A ClauseSpecification instance.

    Returns:
        The query with the specification's WHERE clause applied.
    """
    return query.where(spec.to_clause())


# ---------------------------------------------------------------------------
# Cursor-based pagination
# ---------------------------------------------------------------------------


async def paginate(
    session: AsyncSession,
    query: Select[Any],
    *,
    cursor: str | None,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor_column: InstrumentedAttribute[Any],
    ascending: bool = True,
) -> tuple[list[Any], str | None]:
    """
    Execute a SELECT query with cursor-based pagination.

    The cursor is a base64url-encoded representation of the last item's
    sort-key value. The query is extended with a ``WHERE cursor_column > cursor``
    (ascending) or ``WHERE cursor_column < cursor`` (descending) clause before
    execution.

    Returns a tuple of (items, next_cursor) where:
      - ``items``       is the list of ORM model instances for this page.
      - ``next_cursor`` is the encoded cursor for the next page, or None if
                        this is the last page.

    Args:
        session:        An active ``AsyncSession``.
        query:          The base SELECT statement (already filtered, joined etc).
        cursor:         Opaque cursor from a previous response, or None for page 1.
        limit:          Number of items per page. Clamped to ``MAX_PAGE_SIZE``.
        cursor_column:  The ORM column used for cursor-based ordering (must be
                        unique and monotonically increasing, e.g., ``Model.id``).
        ascending:      Sort direction. True (default) = oldest first (ASC).

    Usage:
        items, next_cursor = await paginate(
            session,
            select(TripModel).where(TripModel.owner_id == user_id),
            cursor=request_cursor,
            limit=20,
            cursor_column=TripModel.id,
        )
        return make_page(items, limit=20, next_cursor=next_cursor)
    """
    limit = min(max(1, limit), MAX_PAGE_SIZE)

    if cursor is not None:
        decoded = decode_cursor(cursor)
        if ascending:
            query = query.where(cursor_column > decoded)
        else:
            query = query.where(cursor_column < decoded)

    if ascending:
        query = query.order_by(asc(cursor_column))
    else:
        query = query.order_by(desc(cursor_column))

    # Fetch one extra to determine whether a next page exists
    query = query.limit(limit + 1)

    result = await session.execute(query)
    rows = list(result.scalars())

    next_cursor: str | None = None
    if len(rows) > limit:
        rows = rows[:limit]
        last_key = getattr(rows[-1], cursor_column.key)
        next_cursor = encode_cursor(str(last_key))

    return rows, next_cursor
