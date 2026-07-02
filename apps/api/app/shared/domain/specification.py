"""
Travix AI — Specification Pattern

A Specification encapsulates a business rule as a reusable, composable
predicate. Specifications can be combined with &, |, and ~ to express
complex conditions without coupling business rules to query language.

Primary use cases:
  1. In-memory filtering of domain objects (always supported).
  2. Translation to SQLAlchemy WHERE clauses (optional — implement in the
     infrastructure layer as a separate SpecificationTranslator).

Design:
  - ABC (abstract base class) rather than Protocol — combinators are
    provided by the base, so inheritance is correct here.
  - Generic in T — the entity type the specification evaluates.
  - Operator overloads (&, |, ~) for readable composition.

Usage — defining a specification:
    from app.shared.domain.specification import Specification
    from app.modules.trips.domain.trip import Trip

    class PublishedTrip(Specification[Trip]):
        def is_satisfied_by(self, candidate: Trip) -> bool:
            return candidate.status == TripStatus.PUBLISHED

    class OwnedByUser(Specification[Trip]):
        def __init__(self, user_id: UUID) -> None:
            self._user_id = user_id

        def is_satisfied_by(self, candidate: Trip) -> bool:
            return candidate.owner_id == self._user_id

Usage — combining specifications:
    published_and_mine = PublishedTrip() & OwnedByUser(current_user.id)
    my_drafts = ~PublishedTrip() & OwnedByUser(current_user.id)

Usage — filtering a collection:
    my_trips = published_and_mine.filter(all_trips)

Usage — in a repository method:
    async def find(self, spec: Specification[Trip]) -> list[Trip]:
        # Option A: fetch all, filter in Python (for small datasets)
        all_trips = await self._fetch_all()
        return list(spec.filter(all_trips))

        # Option B: translate to SQLAlchemy WHERE clause
        where_clause = self._translator.translate(spec)
        ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, Iterable, Iterator, TypeVar

T = TypeVar("T")


class Specification(ABC, Generic[T]):
    """
    Abstract base for all domain specifications.

    Subclasses implement is_satisfied_by(). Combinators are provided here.
    """

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return True if the candidate satisfies this specification."""
        ...

    def filter(self, candidates: Iterable[T]) -> Iterator[T]:
        """Yield candidates that satisfy this specification."""
        return (c for c in candidates if self.is_satisfied_by(c))

    # ------------------------------------------------------------------ #
    # Combinator operators                                                 #
    # ------------------------------------------------------------------ #

    def __and__(self, other: "Specification[T]") -> "AndSpecification[T]":
        """Logical AND: both specifications must be satisfied."""
        return AndSpecification(self, other)

    def __or__(self, other: "Specification[T]") -> "OrSpecification[T]":
        """Logical OR: at least one specification must be satisfied."""
        return OrSpecification(self, other)

    def __invert__(self) -> "NotSpecification[T]":
        """Logical NOT: the specification must not be satisfied."""
        return NotSpecification(self)


# ---------------------------------------------------------------------------
# Composite specifications (private implementation details)
# ---------------------------------------------------------------------------


class AndSpecification(Specification[T]):
    """Both left and right specifications must be satisfied."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)

    def __repr__(self) -> str:
        return f"({self._left!r} & {self._right!r})"


class OrSpecification(Specification[T]):
    """At least one of left or right specifications must be satisfied."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)

    def __repr__(self) -> str:
        return f"({self._left!r} | {self._right!r})"


class NotSpecification(Specification[T]):
    """The wrapped specification must NOT be satisfied."""

    def __init__(self, spec: Specification[T]) -> None:
        self._spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)

    def __repr__(self) -> str:
        return f"(~{self._spec!r})"
