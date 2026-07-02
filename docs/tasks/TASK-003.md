# TASK-003 — FastAPI Foundation (Backend Skeleton)

| Field          | Value                                         |
|----------------|-----------------------------------------------|
| **Status**     | Complete                                      |
| **Type**       | Backend Foundation                            |
| **Priority**   | P0 — Blocks all feature modules               |
| **Assignee**   | Engineering Team                              |
| **Created**    | 2026-06-26                                    |
| **Completed**  | 2026-06-26                                    |
| **Depends on** | TASK-001, TASK-002                            |

---

## Objective

Establish the production-ready FastAPI backend skeleton that every future feature module
builds on. This task refines and extends the infrastructure from TASK-002 with the complete
middleware stack, formal module structure, shared infrastructure utilities, and repository
tooling.

This is **not** a feature implementation. No business logic, no authentication, no users,
no trips, no AI, no maps.

## Scope

**In scope:**
- Canonical middleware location (`app/core/middleware/`) per CLAUDE.md structure
- Request timing middleware (`X-Response-Time` header, slow-request warnings)
- Security headers middleware (X-Content-Type-Options, X-Frame-Options, HSTS in production)
- Cursor-based pagination foundation (`app/core/pagination.py`)
- Monitoring placeholder (`app/core/monitoring.py`) with Sentry lazy initialisation
- Security package placeholder (`app/core/security/`)
- `api_v1_router` — the explicit `APIRouter(prefix="/api/v1")` object in `main.py`
- Updated `main.py` with correct middleware order and monitoring setup
- Sentry DSN configuration fields in `app/config.py`
- Dependabot configuration (`.github/dependabot.yml`)
- Project validation script (`infrastructure/scripts/validate-project.sh`)

**Explicitly out of scope:**
- Authentication (JWT, refresh tokens) — future task
- User module — future task
- Any feature business logic
- Flutter changes of any kind
- Database migrations
- ARQ worker configuration

## Deliverables

### New files
- [x] `apps/api/app/core/middleware/__init__.py`
- [x] `apps/api/app/core/middleware/request_id.py` — canonical implementation
- [x] `apps/api/app/core/middleware/timing.py` — X-Response-Time, slow-request logging
- [x] `apps/api/app/core/middleware/security_headers.py` — HTTP security headers
- [x] `apps/api/app/core/security/__init__.py` — placeholder for auth utilities
- [x] `apps/api/app/core/pagination.py` — CursorPage, encode/decode cursor, make_page()
- [x] `apps/api/app/core/monitoring.py` — Sentry lazy init, monitoring placeholder
- [x] `.github/dependabot.yml` — weekly updates for pip, pub, github-actions, docker
- [x] `infrastructure/scripts/validate-project.sh` — 6-check structural validator

### Updated files
- [x] `apps/api/app/middleware/request_id.py` — shim that re-exports from canonical path
- [x] `apps/api/app/logging_config.py` — updated import to `app.core.middleware.request_id`
- [x] `apps/api/app/config.py` — added `sentry_dsn`, `sentry_traces_sample_rate`, `sentry_profiles_sample_rate`
- [x] `apps/api/app/main.py` — added TimingMiddleware, SecurityHeadersMiddleware, `api_v1_router`, `configure_monitoring()`

## Architecture Notes

### Middleware execution order

FastAPI/Starlette applies middleware in reverse registration order
(last `add_middleware` call = first to execute on inbound requests):

```
Inbound request →  RequestIDMiddleware  (assigns IDs, first to execute)
                →  TimingMiddleware     (starts timer)
                →  SecurityHeadersMiddleware (adds response headers on way out)
                →  CORSMiddleware       (handles preflight, last executed on requests)
                →  Route handler
```

### API v1 router

`api_v1_router = APIRouter(prefix="/api/v1")` is defined in `main.py` and registered
via `app.include_router(api_v1_router)`. When adding a feature module:

```python
# In main.py:
from app.modules.trips.router import router as trips_router
api_v1_router.include_router(trips_router)
```

All feature endpoints automatically receive the `/api/v1/` prefix.
Health endpoints (`/health`, `/ready`, `/live`) remain at the root — they are not
versioned API endpoints and must be reachable by infrastructure tooling.

### Cursor pagination

`CursorPage[T]` and `make_page()` in `app/core/pagination.py` are the shared
types for all collection endpoints. Repositories return `(items, next_cursor)`
tuples and route handlers wrap them in `make_page()`.

### Sentry monitoring

Sentry is disabled by default (no `SENTRY_DSN` set). When `SENTRY_DSN` is
configured in the environment, `configure_monitoring()` initialises Sentry with
FastAPI and SQLAlchemy integrations. The SDK is a lazy import — the application
starts normally without `sentry-sdk` installed.

## Definition of Done

- [x] `make docker-up && curl localhost:8000/health` returns `{"status": "alive"}`
- [x] `curl -I localhost:8000/health` response includes `X-Response-Time`, `X-Content-Type-Options`, `X-Frame-Options`
- [x] `apps/api/app/core/middleware/` contains all three middleware files
- [x] `app/middleware/request_id.py` is a shim (no duplicate implementation)
- [x] `logging_config.py` imports from `app.core.middleware.request_id`
- [x] `api_v1_router` is registered in `main.py`
- [x] `app/core/pagination.py` exports `CursorPage`, `make_page`, `encode_cursor`, `decode_cursor`
- [x] `app/core/monitoring.py` is imported and called in `main.py` lifespan
- [x] `dependabot.yml` covers pip, pub, github-actions, docker
- [x] `validate-project.sh` passes on the current repository state
- [x] No business logic added to any file
- [x] Ruff check passes, no type errors on new files
