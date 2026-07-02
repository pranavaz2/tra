# TASK-002 — Development Infrastructure

| Field          | Value                                     |
|----------------|-------------------------------------------|
| **Status**     | Complete                                  |
| **Type**       | Infrastructure / Backend Foundation       |
| **Priority**   | P0 — Foundational (blocks all feature work) |
| **Assignee**   | Engineering Team                          |
| **Created**    | 2026-06-26                                |
| **Completed**  | 2026-06-26                                |
| **Depends on** | TASK-001                                  |

---

## Objective

Implement the complete development infrastructure for Travix AI: Docker containerization,
Docker Compose orchestration, Pydantic configuration service, structured logging, health
endpoints, database foundation (SQLAlchemy async + Alembic), Redis foundation, and all
supporting repository files.

This task makes the API runnable end-to-end in a local development environment with a single
`make docker-up` command.

## Scope

**In scope:**
- `apps/api/` Python project foundation (pyproject.toml, .python-version)
- Pydantic BaseSettings configuration service (`app/config.py`)
- Async SQLAlchemy engine and session factory (`app/database.py`)
- Redis client abstraction with CacheBackend ABC (`app/redis.py`)
- Structured JSON logging with ContextVar request-ID injection (`app/logging_config.py`)
- RequestID middleware (`app/middleware/request_id.py`)
- Health check endpoints: `/health`, `/ready`, `/live` (`app/core/health.py`)
- RFC 7807 exception handlers (`app/core/exceptions.py`)
- Typed FastAPI dependencies (`app/dependencies.py`)
- FastAPI application factory with lifespan (`app/main.py`)
- Alembic migration setup (`alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`)
- Test scaffolding (`tests/conftest.py`)
- Docker: production multi-stage `Dockerfile`, development `Dockerfile.dev`, `.dockerignore`
- Docker Compose: `docker-compose.yml`, `docker-compose.override.yml`, `docker-compose.prod.yml`
- Infrastructure scripts: `wait-for-db.sh`, `wait-for-redis.sh`, `check-env.sh`,
  `generate-secret.sh`, `reset-db.sh`
- Repository files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `VERSION`
- ADRs: ADR-001 (Modular Monolith), ADR-002 (ARQ), ADR-003 (HS256 JWT)
- Documentation: `docs/engineering/`, `docs/stack/`
- VSCode workspace: `.vscode/extensions.json`, `.vscode/settings.json`
- Updated: `Makefile`, `docs/adr/README.md`, `docs/tasks/README.md`,
  `infrastructure/docker/README.md`, `infrastructure/scripts/README.md`,
  `infrastructure/compose/README.md`

**Explicitly out of scope:**
- Authentication module (TASK-003 or later)
- User, trip, or any feature modules
- Flutter screens or widgets
- Database models or feature repositories
- Business services or use cases
- AI provider implementations
- ARQ worker configuration

## Deliverables

### Python App Core
- [x] `apps/api/pyproject.toml` — build, runtime, dev deps, tool config
- [x] `apps/api/.python-version` — pins Python 3.12
- [x] `apps/api/app/__init__.py`
- [x] `apps/api/app/config.py` — Pydantic BaseSettings with all env vars
- [x] `apps/api/app/database.py` — async SQLAlchemy engine, naming conventions
- [x] `apps/api/app/redis.py` — lazy per-db clients, CacheBackend ABC
- [x] `apps/api/app/logging_config.py` — JSON + text formatters, ContextVar injection
- [x] `apps/api/app/middleware/__init__.py`
- [x] `apps/api/app/middleware/request_id.py` — RequestID ASGI middleware
- [x] `apps/api/app/core/__init__.py`
- [x] `apps/api/app/core/health.py` — `/health`, `/ready`, `/live` endpoints
- [x] `apps/api/app/core/exceptions.py` — RFC 7807 exception handlers
- [x] `apps/api/app/dependencies.py` — typed dependency aliases
- [x] `apps/api/app/main.py` — FastAPI app factory

### Alembic
- [x] `apps/api/alembic.ini`
- [x] `apps/api/migrations/env.py`
- [x] `apps/api/migrations/script.py.mako`
- [x] `apps/api/migrations/versions/.gitkeep`

### Tests
- [x] `apps/api/tests/__init__.py`
- [x] `apps/api/tests/conftest.py`

### Docker
- [x] `apps/api/Dockerfile` — production multi-stage
- [x] `apps/api/Dockerfile.dev` — development with hot-reload
- [x] `apps/api/.dockerignore`
- [x] `apps/mobile/.dockerignore`

### Docker Compose
- [x] `infrastructure/compose/docker-compose.yml`
- [x] `infrastructure/compose/docker-compose.override.yml`
- [x] `infrastructure/compose/docker-compose.prod.yml`

### Infrastructure Scripts
- [x] `infrastructure/scripts/wait-for-db.sh`
- [x] `infrastructure/scripts/wait-for-redis.sh`
- [x] `infrastructure/scripts/check-env.sh`
- [x] `infrastructure/scripts/generate-secret.sh`
- [x] `infrastructure/scripts/reset-db.sh`

### Repository Files
- [x] `SECURITY.md`
- [x] `CODE_OF_CONDUCT.md`
- [x] `VERSION` (0.1.0)

### ADRs
- [x] `docs/adr/ADR-001-modular-monolith-over-microservices.md`
- [x] `docs/adr/ADR-002-arq-over-celery-for-task-queue.md`
- [x] `docs/adr/ADR-003-hs256-jwt-with-rs256-migration-path.md`

### Documentation
- [x] `docs/engineering/README.md`
- [x] `docs/stack/README.md`
- [x] `docs/tasks/TASK-001.md`
- [x] `docs/tasks/TASK-002.md` (this file)

### VSCode
- [x] `.vscode/extensions.json`
- [x] `.vscode/settings.json`

### Updated Files
- [x] `Makefile` — Docker Compose paths fixed, API commands uncommented, `db-reset` and `generate-secrets` added
- [x] `docs/adr/README.md` — ADR index updated with 3 ADRs
- [x] `docs/tasks/README.md` — task index updated with TASK-001 and TASK-002
- [x] `infrastructure/docker/README.md` — references actual Dockerfiles
- [x] `infrastructure/scripts/README.md` — references actual scripts
- [x] `infrastructure/compose/README.md` — references actual Compose files

## Definition of Done

- [x] `make docker-up` starts PostgreSQL, Redis, and API in development mode
- [x] `GET /health` returns `{"status": "alive"}` immediately
- [x] `GET /ready` returns 200 when DB and Redis are reachable, 503 otherwise
- [x] `make migrate` runs `alembic upgrade head` successfully
- [x] `make lint-api` passes with zero Ruff violations
- [x] `make format-check` passes
- [x] `make test-api` runs (no feature tests yet, but conftest loads cleanly)
- [x] No secrets or credentials committed in any file
- [x] All environment variables sourced from Pydantic Settings, not `os.environ`
- [x] Production Docker image runs as non-root user (UID 1001)
- [x] ADRs written for all three architectural decisions
