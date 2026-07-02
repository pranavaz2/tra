# TASK-005 — Database Foundation

**Status:** Complete
**Phase:** 1 — Milestone 1
**Depends on:** TASK-003.2 (Shared Kernel Foundation)
**Blocks:** TASK-006+ (all feature modules)

---

## Objective

Build the production-ready persistence foundation that all feature modules
will build upon. This is a platform task — no business logic, no feature
models, no authentication.

---

## Scope

### In Scope

- SQLAlchemy 2.x async engine with full pool configuration
- `DeclarativeBase` with enforced naming conventions
- ORM column mixins: UUID PK, timestamps, soft-delete, optimistic locking
- `SQLAlchemyRepository[E, IDT]` generic base implementation
- `UnitOfWork` Protocol + `SQLAlchemyUnitOfWork` implementation
- Query helpers: sort, filter, specification bridge, cursor pagination
- SQLAlchemy engine event hooks for query timing and slow query logging
- Test fixtures: `db_engine`, `db_session` (rollback isolation), `uow_factory`
- Test helpers: `count_rows`, `exists_by_id`, `RepositoryTestCase`
- `migrations/README` with complete operational guide
- Architecture documentation with Mermaid diagrams

### Explicitly Out of Scope

- Authentication / Users / Trips / AI / Maps / Budget modules
- Business entities or feature-specific repositories
- First Alembic migration (no schema change yet — no models exist)
- Redis infrastructure (separate task)

---

## Deliverables

### New Files

| File | Purpose |
|---|---|
| `app/core/db/__init__.py` | Package with import discipline documentation |
| `app/core/db/mixins.py` | `UUIDPrimaryKeyMixin`, `TimestampMixin`, `SoftDeleteMixin`, `OptimisticLockMixin` |
| `app/core/db/events.py` | `register_query_hooks()` for query timing + slow query logging |
| `app/core/db/repository.py` | `SQLAlchemyRepository[E, IDT]` with CRUD + convenience methods |
| `app/core/db/unit_of_work.py` | `UnitOfWork` Protocol + `SQLAlchemyUnitOfWork` with savepoint support |
| `app/core/db/query.py` | `SortSpec`, `apply_sort`, `exclude_deleted`, `ClauseSpecification`, `paginate` |
| `tests/helpers/__init__.py` | Test helpers package |
| `tests/helpers/db.py` | `count_rows`, `count_active`, `exists_by_id`, `soft_delete`, `RepositoryTestCase` |
| `migrations/README` | Full operational guide for Alembic |
| `docs/architecture/database.md` | Architecture docs + Mermaid diagrams |

### Modified Files

| File | Change |
|---|---|
| `app/config.py` | Added `db_slow_query_threshold_ms: float = 200.0` |
| `app/database.py` | Registered `register_query_hooks()` in `_build_engine()`, improved docs |
| `tests/conftest.py` | Replaced TODO stubs with `db_engine`, `db_session`, `uow_factory` fixtures |

---

## Architecture Decisions

### `app/core/db/` — not `app/infrastructure/`

The new subdirectory lives under `app/core/` (cross-cutting concerns) not at
a new top-level directory. This respects CLAUDE.md §15 rule 3 ("implement within
the defined module structure") while grouping persistence infrastructure alongside
other cross-cutting concerns.

### One-class entities (ORM model = domain entity)

Feature modules use a single class that is both the SQLAlchemy ORM model and
the domain entity. This is a pragmatic choice for a modular monolith at this
scale — full two-class separation (ORM model + domain entity + mapper) adds
significant complexity with minimal benefit when the database is the single
source of truth and domain logic is not so complex that it needs to be isolated
from persistence concerns.

The `SQLAlchemyRepository[E, IDT]` base is generic enough to work with either
approach if the architecture evolves toward full model-entity separation.

### `save()` calls `flush()`, not `commit()`

`flush()` writes changes to the database within the current transaction without
committing. This keeps the caller in control of the commit boundary. Route
handlers commit via `get_db_session()`, use cases commit via `UnitOfWork`.
Neither the repository nor the entity decides when to commit.

### `paginate()` fetches N+1 rows

To determine whether a next page exists, the cursor pagination helper fetches
`limit + 1` rows and discards the last one. The alternative (COUNT query) is
heavier and gives a potentially stale result in concurrent systems.

### Test isolation via outer transaction rollback

The `db_session` fixture starts an outer transaction on the raw connection,
creates an `AsyncSession` bound to it, yields the session to the test, and
rolls back the outer transaction regardless of what the test did. This avoids
table truncation between tests and is faster than recreating the schema.

---

## Definition of Done

- [x] `app/core/db/` created with 5 modules + `__init__.py`
- [x] `config.py` updated with `db_slow_query_threshold_ms`
- [x] `database.py` registers event hooks in `_build_engine()`
- [x] `tests/conftest.py` `db_engine` and `db_session` fully implemented
- [x] `tests/helpers/db.py` created with assertion helpers
- [x] `migrations/README` covers all operational scenarios
- [x] `docs/architecture/database.md` with 3 Mermaid diagrams
- [x] No business models, no authentication, no feature code
- [x] No synchronous SQLAlchemy in application code
- [x] No circular imports between modules
- [x] Type hints on every function signature and class attribute
- [x] No `print()`, no `os.environ`, no hardcoded secrets
