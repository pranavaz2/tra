# TASK-3.1 - Locations Foundation

## Objective

Establish the backend foundation for canonical travel locations in Travix AI. This creates
the `locations` feature module as the source of truth for destinations, places, and
geo-aware lookup primitives used by trips, itineraries, maps, weather, and AI planning.

## Scope

- Create the `apps/api/app/modules/locations/` vertical slice.
- Define core Location domain concepts using Travix terminology.
- Add async repository and service boundaries for location lookup and persistence.
- Add SQLAlchemy 2.0 models for locations with PostGIS geometry support.
- Add Alembic migration for the locations schema, including required GiST indexes.
- Add API schemas and authenticated `/api/v1/locations` read endpoints.
- Keep all maps or geocoding provider access behind `app/services/maps/`.

## Files Expected

- `apps/api/app/modules/locations/__init__.py`
- `apps/api/app/modules/locations/router.py`
- `apps/api/app/modules/locations/schemas.py`
- `apps/api/app/modules/locations/service.py`
- `apps/api/app/modules/locations/repository.py`
- `apps/api/app/modules/locations/models.py`
- `apps/api/app/modules/locations/exceptions.py`
- `apps/api/migrations/versions/{revision}_create_locations.py`
- `apps/api/tests/unit/locations/test_location_service.py`
- `apps/api/tests/unit/locations/test_location_repository.py`
- `apps/api/tests/integration/locations/test_locations_api.py`

## Out of Scope

- Flutter UI or mobile data-layer changes.
- Trip, itinerary, booking, or recommendation features.
- AI-generated factual location data.
- Provider-specific maps SDK usage inside the locations module.
- Background ingestion pipelines or bulk import tooling.
- Admin moderation workflows.

## Acceptance Criteria

- Locations are modeled inside a dedicated `locations` feature module.
- Location persistence uses async SQLAlchemy 2.0 style with `Mapped[]` and
  `mapped_column()`.
- Geometry columns use PostGIS and have GiST indexes in the same new migration.
- User-facing location records include `created_at`, `updated_at`, and `deleted_at`.
- Repository methods expose async data access only; no route handler writes SQL directly.
- Service methods contain business orchestration and never depend on FastAPI.
- API endpoints return explicit Pydantic response models wrapped in the approved response
  shape.
- All external maps/geocoding interactions go through `app/services/maps/`.
- Module boundaries are respected with no circular imports.

## Definition of Done

- `TASK-3.1` implementation matches this specification.
- New schema changes are delivered through a new Alembic migration only.
- `ruff check .` passes for backend code.
- `black --check .` passes for backend code.
- Relevant unit and integration tests pass.
- No source files outside the locations slice, router registration, service abstractions,
  migration, and tests are changed unless required by architecture.
- No Flutter source code is modified.

## Testing Requirements

- Unit tests cover location service behavior and expected failure cases.
- Unit tests cover repository query methods, including soft-delete filtering.
- Integration tests use PostgreSQL with PostGIS enabled.
- API tests verify response schemas, authentication behavior, and RFC 7807 error shape.
- Tests must not call live maps, geocoding, AI, or weather providers.
