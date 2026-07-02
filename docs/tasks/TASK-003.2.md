# TASK-003.2 — Shared Kernel Foundation

**Status:** Complete
**Phase:** 1 — Milestone 1
**Depends on:** TASK-003.1 (FastAPI Foundation)
**Blocks:** All feature module tasks (TASK-004+)

---

## Objective

Create the reusable DDD-inspired domain building blocks (shared kernel) that every backend
feature module will use. These are the domain primitives — no business logic, no feature
code, no SQLAlchemy models, no FastAPI endpoints, no authentication.

---

## Scope

### In scope

- `app/shared/domain/` — pure Python domain abstractions (no framework imports)
- `app/shared/infrastructure/` — vendor-neutral infrastructure interfaces with stdlib-only
  default implementations
- `app/shared/application/` — ApplicationContext for use-case wiring and ARQ workers
- `app/shared/presentation/` — shared Pydantic base schemas for request/response models
- Updated `app/dependencies.py` — typed aliases for shared infrastructure providers

### Explicitly out of scope

- No SQLAlchemy models
- No FastAPI endpoints or routers
- No authentication or authorization
- No business logic of any kind
- No feature module code

---

## Deliverables

### `app/shared/domain/`

| File | Purpose |
|---|---|
| `errors.py` | Full exception hierarchy rooted at `TravixError` |
| `result.py` | `Success[T]` / `Failure[E]` result type + PEP 695 type aliases |
| `entity.py` | `Entity[IDT]` base dataclass with identity-based equality |
| `aggregate.py` | `AggregateRoot[IDT]` extending Entity with domain event tracking |
| `value_object.py` | `ValueObject` marker base class for frozen dataclasses |
| `events.py` | `DomainEvent` frozen dataclass base for all domain events |
| `repository.py` | `Repository[E, ID]` async Protocol for data access abstraction |
| `specification.py` | `Specification[T]` ABC with `&`, `|`, `~` combinators |

### `app/shared/infrastructure/`

| File | Purpose |
|---|---|
| `clock.py` | `Clock` Protocol + `SystemClock` (prod) + `FixedClock` (test) |
| `uuid_provider.py` | `UuidProvider` Protocol + `DefaultUuidProvider` + `FixedUuidProvider` + `SequentialUuidProvider` |
| `random_provider.py` | `RandomProvider` Protocol + `DefaultRandomProvider` + `SeededRandomProvider` |

### `app/shared/application/`

| File | Purpose |
|---|---|
| `context.py` | `ApplicationContext` frozen dataclass; `.default()` and `.testing()` classmethods |

### `app/shared/presentation/`

| File | Purpose |
|---|---|
| `schemas.py` | `BaseSchema`, `IDSchema`, `TimestampedSchema`, `EmptyResponse`, `MessageResponse` |

### `app/dependencies.py` (updated)

Added typed aliases:
- `CurrentClock` — `Annotated[Clock, Depends(get_clock)]`
- `CurrentUuidProvider` — `Annotated[UuidProvider, Depends(get_uuid_provider)]`
- `CurrentRandomProvider` — `Annotated[RandomProvider, Depends(get_random_provider)]`
- `AppContext` — `Annotated[ApplicationContext, Depends(get_app_context)]`

---

## Architecture Notes

### Import discipline (strictly enforced)

```
app.shared.domain.*        → pure Python only. No stdlib with side effects.
app.shared.infrastructure.* → stdlib only. No SQLAlchemy, no Redis, no external packages.
app.shared.application.*   → may import domain + infrastructure abstractions only.
app.shared.presentation.*  → may import Pydantic and domain type references only.
```

Feature modules import FROM the shared kernel. The shared kernel NEVER imports from
feature modules. This is a one-way dependency boundary.

### Result Pattern

The `Result[T]` type alias enables use cases to signal expected failures without exceptions:

```python
type Result[T] = Success[T] | Failure[TravixError]

match await service.find_trip(trip_id):
    case Success(value=trip):
        return TripResponse.model_validate(trip)
    case Failure(error=NotFoundError()):
        raise HTTPException(status_code=404)
```

`TravixError` (and all subclasses) is still a real Python exception — it can be raised
directly when appropriate. The Result pattern is for expected, business-level failures.
Unexpected failures (bugs, infrastructure failures) should still propagate as exceptions.

### ApplicationContext

The `ApplicationContext` dataclass solves two problems:
1. FastAPI DI is not available in ARQ background workers. `ApplicationContext.default()`
   provides the same dependencies without the DI graph.
2. `ApplicationContext.testing()` creates a deterministic context in a single line, removing
   boilerplate from every test.

### Test implementations

Every infrastructure interface has at least one test implementation:

| Protocol | Production | Test |
|---|---|---|
| `Clock` | `SystemClock` | `FixedClock` |
| `UuidProvider` | `DefaultUuidProvider` | `FixedUuidProvider`, `SequentialUuidProvider` |
| `RandomProvider` | `DefaultRandomProvider` | `SeededRandomProvider` |

---

## Definition of Done

- [x] All files created with correct content and import discipline
- [x] `app/shared/domain/` — 8 files, zero external imports
- [x] `app/shared/infrastructure/` — 3 files + `__init__.py`, stdlib only
- [x] `app/shared/application/context.py` — `default()` and `testing()` classmethods
- [x] `app/shared/presentation/schemas.py` — 5 schema classes, Pydantic v2 only
- [x] `app/dependencies.py` — 4 new typed aliases wired to provider functions
- [x] No business logic introduced
- [x] No SQLAlchemy, FastAPI routing, or authentication code
- [x] Named conventions follow CLAUDE.md §8
- [x] Type hints on every function and class attribute
- [x] `async def` used only where I/O is performed (none here — kernel is pure)
