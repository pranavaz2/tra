# Trips Module

Owns the `Trip` aggregate — the central entity of the Travel context.

Every other Travel module references a `TripId` but does not own the trip itself.

## Layer responsibilities

### `domain/`
Pure business logic with zero external dependencies.

- `entities/` — `Trip` aggregate root. Owns status, metadata, privacy, and version counter.
- `value_objects/` — `TripId`, `TripTitle`, `TripDateRange`, `TripStatus`, `TripPrivacy`.
- `repositories/` — `ITripRepository` abstract interface. No SQL here.
- `services/` — Domain services that operate on `Trip` entities (e.g., `TripAccessPolicy`).
- `events/` — Domain events: `TripCreated`, `TripUpdated`, `TripStatusChanged`, `TripDeleted`, `TripActivated`, `TripCompleted`.

### `application/`
Use case orchestration. Depends on domain interfaces only.

- `commands/` — Write-side command objects: `CreateTripCommand`, `UpdateTripCommand`, `DeleteTripCommand`, `ChangeTripStatusCommand`.
- `queries/` — Read-side query objects: `GetTripQuery`, `ListTripsQuery`, `GetSharedTripQuery`.
- `handlers/` — Command and query handlers. One handler per command or query.
- `services/` — Application services composed from repository and domain service dependencies.
- `dtos/` — Internal data transfer objects for command/query payloads not covered by schemas.

### `infrastructure/`
Concrete implementations of domain interfaces.

- `models/` — SQLAlchemy ORM models (`TripModel`). Uses `Mapped[]` and `mapped_column()` (2.0 style).
- `repositories/` — `SQLAlchemyTripRepository` implementing `ITripRepository`.
- `dependencies.py` — FastAPI `Depends` factories for injecting repositories and services.

### `presentation/`
HTTP boundary. No business logic.

- `router.py` — FastAPI `APIRouter`. Routes only — delegates immediately to application services.
- `schemas.py` — Pydantic request and response models. All endpoints have explicit models.
- `error_responses.py` — RFC 7807 Problem Details error response definitions for this module.

### `tests/`
- `unit/` — Tests for domain entities, value objects, and application services (mocked repositories).
- `integration/` — Tests using a real PostgreSQL instance. No mocked repositories.

## Invariants

- A `Trip` stores only metadata. Destination lists are derived from Itinerary via projections.
- The `version` field is used for optimistic concurrency — increment on every mutation.
- Soft delete: `deleted_at` timestamp. Hard deletes are never performed.
