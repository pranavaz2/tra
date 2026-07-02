# apps/api/ — Travix AI FastAPI Backend

This directory contains the **FastAPI backend** for Travix AI.

---

## Overview

The API is the **single source of business logic** for Travix AI. It owns:

- All business rules and validations
- AI orchestration (via provider abstraction)
- Database reads and writes
- External service integration (maps, weather, email, storage, notifications)
- Authentication and authorization
- Background job scheduling

The Flutter app calls this API. The API makes decisions; Flutter displays them.

---

## Architecture

The backend follows a **Modular Monolith** with **Vertical Slice Architecture**:

```
app/
├── main.py                     # FastAPI application factory
├── config.py                   # Pydantic BaseSettings (all config here)
├── dependencies.py             # Shared FastAPI dependencies
├── database.py                 # Async engine, session factory, base model
│
├── modules/                    # Feature modules — one per domain concept
│   └── {module_name}/
│       ├── router.py           # Routes only — no logic
│       ├── schemas.py          # Pydantic request/response models
│       ├── service.py          # Business logic and orchestration
│       ├── repository.py       # SQLAlchemy queries — data access only
│       ├── models.py           # SQLAlchemy ORM models
│       └── exceptions.py       # Module-specific exception classes
│
├── core/                       # Cross-cutting infrastructure
│   ├── security/               # JWT, password hashing, token management
│   ├── exceptions/             # Global exception handlers
│   ├── middleware/             # CORS, logging, auth middleware
│   └── pagination.py          # Cursor-based pagination utilities
│
└── services/                   # External service abstraction layer
    ├── ai/                     # AI provider (base + concrete + factory)
    ├── maps/                   # Maps provider
    ├── storage/                # Object storage provider
    ├── email/                  # Email provider
    ├── weather/                # Weather provider
    └── notifications/          # Push notification provider
```

See `CLAUDE.md` Section 5 for the complete directory structure specification.

---

## Technology

| Technology | Purpose |
|---|---|
| Python 3.12+ | Language |
| FastAPI | Async web framework |
| SQLAlchemy 2.0 (async) | ORM — `Mapped[]` and `mapped_column()` |
| Alembic | Database migrations |
| PostgreSQL 16 + PostGIS | Primary database with spatial extensions |
| Pydantic v2 | Validation — `model_config = ConfigDict(...)` |
| ARQ | Async task queue backed by Redis |
| Redis 7 | Cache, task queue broker, token revocation |

---

## Key Rules

These rules are non-negotiable. See `CLAUDE.md` for the complete list.

- **All routes prefixed `/api/v1/`.**
- **All endpoints have Pydantic request and response models.** Never return raw dicts.
- **All database operations use `async def` and `AsyncSession`.**
- **All external calls go through `app/services/`** — never import provider SDKs directly.
- **Never edit an existing Alembic migration.** Always create a new one.
- **Every PostGIS geometry column has a GiST index** in the same migration.

---

## Local Development

```bash
# Create and activate virtual environment
cd apps/api
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Apply database migrations (requires PostgreSQL running via Docker)
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests (requires PostgreSQL + Redis running)
pytest tests/ -v

# Lint
ruff check .
black --check .

# Format
black . && isort .
```

---

## API Documentation

When the server is running:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI JSON:** `http://localhost:8000/openapi.json`

---

## Status

> This directory will be bootstrapped as part of TASK-002 (API Bootstrap).
> The FastAPI project does not yet exist — it will be initialized during that task.
