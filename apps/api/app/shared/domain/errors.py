"""
Travix AI — Domain Error Hierarchy

Structured error types that represent EXPECTED failure states. These are
not bugs — they are valid outcomes of business operations that the caller
must handle.

Usage with the Result pattern (preferred):
    from app.shared.domain.result import Failure, Success
    from app.shared.domain.errors import NotFoundError

    async def get_trip(trip_id: UUID) -> Success[Trip] | Failure[NotFoundError]:
        trip = await repository.find_by_id(trip_id)
        if trip is None:
            return Failure(NotFoundError("trip", trip_id))
        return Success(trip)

Usage as exceptions (for truly unexpected failures):
    from app.shared.domain.errors import InfrastructureError
    raise InfrastructureError("Redis connection lost")

HTTP mapping (applied in app.core.exceptions):
    ValidationError     → 422 Unprocessable Entity
    NotFoundError       → 404 Not Found
    UnauthorizedError   → 401 Unauthorized
    ForbiddenError      → 403 Forbidden
    ConflictError       → 409 Conflict
    DomainError         → 422 Unprocessable Entity (business rule violation)
    InfrastructureError → 503 Service Unavailable
    ApplicationError    → 500 Internal Server Error (unexpected)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class TravixError(Exception):
    """
    Root of the Travix AI error hierarchy.

    All structured errors inherit from this class. Catching TravixError
    catches every expected application failure; catching a subclass gives
    precision.

    Attributes:
        code:    Machine-readable snake_case identifier (e.g. "not_found").
        message: Human-readable description for logging and API responses.
    """

    code: str = "error"

    def __init__(self, message: str = "") -> None:
        self.message = message or self.__class__.__doc__ or "An error occurred."
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# Validation — input failed a business or technical constraint
# ---------------------------------------------------------------------------


class ValidationError(TravixError):
    """Request input failed validation."""

    code = "validation_error"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        value: Any = None,
    ) -> None:
        super().__init__(message)
        self.field = field
        self.value = value


# ---------------------------------------------------------------------------
# Domain — a business invariant was violated
# ---------------------------------------------------------------------------


class DomainError(TravixError):
    """A business rule or invariant was violated."""

    code = "domain_error"


# ---------------------------------------------------------------------------
# Application — expected application-level failures
# ---------------------------------------------------------------------------


class ApplicationError(TravixError):
    """Application-level expected failure (not a bug, not a business rule)."""

    code = "application_error"


class NotFoundError(ApplicationError):
    """The requested resource does not exist."""

    code = "not_found"

    def __init__(self, resource: str, id: UUID | str | int | None = None) -> None:
        suffix = f" with id={id!r}" if id is not None else ""
        super().__init__(f"{resource}{suffix} not found.")
        self.resource = resource
        self.resource_id = id


class UnauthorizedError(ApplicationError):
    """The request lacks valid authentication credentials."""

    code = "unauthorized"

    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__(message)


class ForbiddenError(ApplicationError):
    """The authenticated user does not have permission to perform this action."""

    code = "forbidden"

    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__(message)


class ConflictError(ApplicationError):
    """The request conflicts with the current state of the resource."""

    code = "conflict"

    def __init__(self, message: str) -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Infrastructure — external system failures
# ---------------------------------------------------------------------------


class InfrastructureError(TravixError):
    """
    An external infrastructure dependency failed (database, Redis, third-party API).

    These are NOT retried by the caller — they propagate to the unhandled
    exception handler and are logged as 5xx errors.
    """

    code = "infrastructure_error"

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class DatabaseError(InfrastructureError):
    """Database query or transaction failed."""

    code = "database_error"


class CacheError(InfrastructureError):
    """Cache read or write failed."""

    code = "cache_error"


class ExternalServiceError(InfrastructureError):
    """A call to an external API (AI, maps, weather, etc.) failed."""

    code = "external_service_error"

    def __init__(
        self,
        service: str,
        message: str,
        *,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(f"[{service}] {message}", cause=cause)
        self.service = service
