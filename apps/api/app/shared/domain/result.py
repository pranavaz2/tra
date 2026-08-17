"""
Travix AI — Result Pattern

Explicit success/failure types for service and use-case return values.

The Result pattern replaces exceptions for EXPECTED failures. It forces
callers to handle both outcomes rather than leaving failures implicit.

    # Producing a result
    async def find_trip(trip_id: UUID) -> Result[Trip]:
        trip = await repo.find_by_id(trip_id)
        return Success(trip) if trip else Failure(NotFoundError("trip", trip_id))

    # Consuming a result
    result = await find_trip(trip_id)
    if result.is_ok:
        return TripResponse.model_validate(result.value)
    raise_http_for(result.error)

    # Or with Python 3.10+ structural pattern matching
    match result:
        case Success(value=trip):
            return TripResponse.model_validate(trip)
        case Failure(error=NotFoundError() as err):
            raise HTTPException(status_code=404, detail=err.message)

Type aliases:
    Result[T]           — shorthand: Success[T] | Failure[TravixError]
    TypedResult[T, E]   — when the error type should be explicit

Note: Failure.unwrap() raises the contained error as an exception, providing
an escape hatch when callers know a result must be successful (e.g. in tests).
"""

from __future__ import annotations

from typing import Callable, Generic, Literal, Never, TypeVar, final

from app.shared.domain.errors import TravixError

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E", bound=TravixError)


@final
class Success(Generic[T]):
    """
    Represents a successful outcome.

    Attributes:
        value: The result value.
    """

    __slots__ = ("_value",)
    __match_args__ = ("value",)

    def __init__(self, value: T) -> None:
        self._value = value

    @property
    def value(self) -> T:
        """The wrapped success value."""
        return self._value

    @property
    def is_ok(self) -> Literal[True]:
        return True

    def unwrap(self) -> T:
        """Return the value (always succeeds for Success)."""
        return self._value

    def map(self, fn: Callable[[T], U]) -> "Success[U]":
        """Transform the value with fn, returning a new Success."""
        return Success(fn(self._value))

    def __repr__(self) -> str:
        return f"Success({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Success):
            return self._value == other._value  # type: ignore[attr-defined]
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Success", self._value))


@final
class Failure(Generic[E]):
    """
    Represents a failed outcome.

    Attributes:
        error: The structured error describing the failure.
    """

    __slots__ = ("_error",)
    __match_args__ = ("error",)

    def __init__(self, error: E) -> None:
        self._error = error

    @property
    def error(self) -> E:
        """The wrapped error."""
        return self._error

    @property
    def is_ok(self) -> Literal[False]:
        return False

    def unwrap(self) -> Never:
        """
        Raise the contained error as an exception.

        Use only when the caller is certain the result is a Success and the
        Failure case represents a programming error, not an expected outcome.
        """
        raise self._error

    def map(self, fn: object) -> "Failure[E]":
        """map is a no-op on Failure — the error propagates unchanged."""
        return self

    def __repr__(self) -> str:
        return f"Failure({self._error!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Failure):
            return self._error == other._error  # type: ignore[attr-defined]
        return NotImplemented

    def __hash__(self) -> int:
        return hash(("Failure", type(self._error).__name__))


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Result[T] — the common case: success carries T, failure carries any TravixError
# Used in most service and use-case return types.
# Example: async def create_trip(...) -> Result[Trip]
from typing import Any, TypeAlias

Result: TypeAlias = "Success[Any] | Failure[TravixError]"

# TypedResult[T, E] — when the error type should be precise for type narrowing.
# Example: async def validate_email(...) -> TypedResult[str, ValidationError]
TypedResult: TypeAlias = "Success[Any] | Failure[Any]"
