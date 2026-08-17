# Itinerary Module

Owns the `Itinerary` aggregate and related child entities `ItineraryDay` and `ItineraryItem`.

Each `Trip` owns a single `Itinerary` (1-to-1 relationship). 

## Layer responsibilities

### `domain/`
Pure business logic with zero external dependencies.

- `entities/` — `Itinerary` aggregate root, `ItineraryDay` entity, `ItineraryItem` entity.
- `value_objects/` — `ItineraryId`, `ItineraryDayId`, `ItineraryItemId`, `ItemTitle`, `ItineraryItemType` (Enum).
- `repositories/` — `IItineraryRepository` Protocol interface.
- `events/` — Domain events: `ItineraryCreated`, `ItineraryDayAdded`, `ItineraryDayRemoved`, `ItineraryItemAdded`, etc.

### `application/`
CQRS use case orchestration.

- `commands/` — CQRS write-side commands carrying raw input payloads.
- `queries/` — CQRS read-side queries.
- `handlers/` — Command and query handlers executing service logic.
- `itinerary_service.py` — Orchestrates transaction boundary, aggregate mapping, validation, and auto-creation of empty itineraries on first read.

### `infrastructure/`
Persistence mapping and dependency injection setups.

- `models/` — SQLAlchemy 2.0 ORM tables: `itineraries`, `itinerary_days`, and `itinerary_items`.
- `repositories/` — `SQLAlchemyItineraryRepository` implementing mapping.
- `dependencies.py` — FastAPI Depends factories for injecting dependencies.

### `presentation/`
FastAPI endpoints and validation schemas.

- `router.py` — FastAPI endpoints routing itineraries, day management, and day items.
- `schemas.py` — Pydantic v2 transport models.
- `error_responses.py` — RFC 7807 problem details error mapping.
