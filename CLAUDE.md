# CLAUDE.md — Travix AI Engineering Guide

This file is the **authoritative engineering reference** for all work on Travix AI.
Every task — whether performed by a human engineer or an AI agent — must comply fully with
this document before any code is written, reviewed, or merged.

Read this file completely before starting any task.

---

## 1. Project Context

**Name:** Travix AI
**Type:** AI-powered travel planning platform
**Phase:** Active development — production-grade from day one
**Repository type:** Monorepo (Flutter + FastAPI)

Travix AI allows users to plan, explore, and experience travel through AI-generated
itineraries, real-time weather integration, interactive maps, and intelligent suggestions.
The system is designed for scale, security, and long-term maintainability.

---

## 2. Repository Structure

```
travix-ai/
├── apps/
│   ├── mobile/          # Flutter application — presentation only
│   └── api/             # FastAPI application — all business logic lives here
├── packages/            # Shared internal packages (Dart and/or Python)
├── docs/
│   ├── product-bible/   # Product requirements, vision, and feature definitions
│   ├── adr/             # Architecture Decision Records (permanent, append-only)
│   ├── architecture/    # System diagrams and architecture documentation
│   ├── api/             # API contracts and endpoint documentation
│   ├── decisions/       # Engineering decisions that don't warrant a full ADR
│   ├── tasks/           # Engineering task specifications (source of truth per task)
│   └── diagrams/        # Mermaid, draw.io, or image-based system diagrams
├── infrastructure/
│   ├── docker/          # Dockerfiles for each service
│   ├── compose/         # Docker Compose files (local dev, CI, production)
│   └── scripts/         # Developer and CI utility scripts
└── .github/             # GitHub Actions workflows and repository templates
```

---

## 3. Technology Stack

### Mobile (`apps/mobile/`)
| Technology | Version | Purpose |
|---|---|---|
| Flutter | Stable channel, latest | Cross-platform mobile framework |
| Riverpod | 2.x | State management — always use `@riverpod` code generation |
| GoRouter | Latest stable | Declarative navigation |
| Dio | Latest stable | HTTP client with interceptors |
| Drift | Latest stable | Reactive local SQLite ORM for offline support |
| Material 3 | Flutter built-in | Design system |

### Backend (`apps/api/`)
| Technology | Version | Purpose |
|---|---|---|
| Python | 3.12+ | Language |
| FastAPI | Latest stable | Async web framework |
| SQLAlchemy | 2.0 (async) | ORM — always use `Mapped[]` and `mapped_column()` |
| Alembic | Latest stable | Database migrations |
| PostgreSQL | 16+ | Primary relational database |
| PostGIS | 3.x | Spatial extensions for PostgreSQL |
| Pydantic | v2 | Validation — always use `model_config = ConfigDict(...)` |
| ARQ | Latest stable | Async task queue backed by Redis |
| Redis | 7+ | Cache, task queue broker, token revocation list |

### Infrastructure
| Technology | Purpose |
|---|---|
| Docker | Containerization for all services |
| Docker Compose | Local development orchestration |
| GitHub Actions | CI/CD pipeline |

---

## 4. Architecture Principles

These are non-negotiable. Every engineering decision must align with every principle listed
below. When in doubt, prioritize in the order listed.

### 4.1 Clean Architecture

Dependencies flow strictly inward:

```
Presentation → Application → Domain → Infrastructure
```

- The **domain layer** contains business entities, value objects, and repository interfaces.
  It has zero external dependencies.
- The **application layer** contains use cases and service orchestration.
- The **infrastructure layer** implements interfaces defined in domain/application layers.
- The **presentation layer** (Flutter) calls the API. Nothing more.

### 4.2 Vertical Slice Architecture

- Code is organized by **feature**, not by layer.
- Each feature owns its routes, schemas, services, repositories, and models in a single module.
- Shared concerns (auth, pagination, error handling) live in `app/core/`.
- Cross-feature dependencies are rare and must go through domain interfaces only.

### 4.3 Modular Monolith

- The backend is a **single deployable unit** divided into isolated feature modules.
- Module boundaries are enforced through Python package structure and import discipline.
- No circular imports between feature modules. Ever.
- Module internal code is private by convention — only expose what is explicitly intended.

### 4.4 Domain-Driven Design

- Use **ubiquitous language**: terms in code must match terms in the product specification and
  the product bible. If the product says "Trip", the entity is `Trip`, not `Journey` or `Plan`.
- **Entities** have identity (a unique ID that persists over time).
- **Value Objects** have no identity — they are defined by their attributes.
- **Aggregates** enforce consistency boundaries. Only the root can be persisted directly.
- **Repositories** abstract all data access. Feature code never writes SQL directly (except for
  PostGIS spatial queries where the ORM cannot express the query).

### 4.5 Backend Owns Business Logic

- The Flutter app is **presentation only**.
- Business rules, calculations, validations, and AI orchestration live exclusively in the API.
- Flutter validates for **UX only** (e.g., "this field cannot be empty"). Never for business
  correctness (e.g., "a trip must have at least one destination").
- If a business rule needs to change, only the API changes.

### 4.6 Every External Service Behind an Abstraction

- Every external service is accessed through an **internal interface** defined in
  `apps/api/app/services/`.
- Feature modules import only from the service abstraction layer, never from provider SDKs.
- Concrete implementations are injected via FastAPI dependency injection.
- The active provider is selected via environment variable (e.g., `AI_PROVIDER=openai`).

### 4.7 Replaceable AI Provider

- The AI provider abstraction interface must not leak any provider-specific concepts.
- A `MockAIProvider` must exist for local development and testing — no developer should need
  a live AI API key to build features.
- Switching AI providers requires only a new concrete implementation and a config change.

### 4.8 Security by Design

- Authentication and authorization are applied at the infrastructure/middleware layer.
- Input validation is applied at the API boundary via Pydantic — every endpoint has explicit
  request and response models.
- Secrets never appear in code or version control.
- Token revocation is supported via Redis.

### 4.9 Performance by Design

- All database operations are async.
- Slow operations (AI calls, external API calls, file processing) are offloaded to the ARQ
  task queue. The API responds with a job ID; the client polls or receives a push notification.
- PostGIS geometry columns always have GiST indexes.
- Redis is used for response caching on expensive reads.

---

## 5. Backend Module Structure (`apps/api/`)

```
apps/api/
├── app/
│   ├── main.py                    # FastAPI application factory
│   ├── config.py                  # Pydantic BaseSettings — all config here
│   ├── dependencies.py            # Shared FastAPI dependencies (db session, current user)
│   ├── database.py                # Async engine, session factory, base model
│   │
│   ├── modules/                   # Feature modules (Vertical Slice)
│   │   └── {module_name}/
│   │       ├── __init__.py
│   │       ├── router.py          # FastAPI APIRouter — routes only, no logic
│   │       ├── schemas.py         # Pydantic request/response models
│   │       ├── service.py         # Business logic and orchestration
│   │       ├── repository.py      # Data access — SQLAlchemy queries only
│   │       ├── models.py          # SQLAlchemy ORM models
│   │       └── exceptions.py      # Module-specific exception classes
│   │
│   ├── core/                      # Cross-cutting infrastructure concerns
│   │   ├── security/              # JWT creation, validation, password hashing
│   │   ├── exceptions/            # Global exception handlers and error schemas
│   │   ├── middleware/            # CORS, request logging, auth middleware
│   │   └── pagination.py          # Shared cursor-based pagination
│   │
│   └── services/                  # External service abstraction layer
│       ├── ai/
│       │   ├── base.py            # AIProvider abstract interface
│       │   ├── mock.py            # MockAIProvider for testing
│       │   └── factory.py         # Provider selection by config
│       ├── maps/
│       │   ├── base.py            # MapsProvider abstract interface
│       │   └── factory.py
│       ├── storage/
│       │   ├── base.py            # StorageProvider abstract interface
│       │   └── factory.py
│       ├── email/
│       │   ├── base.py            # EmailProvider abstract interface
│       │   └── factory.py
│       ├── weather/
│       │   ├── base.py            # WeatherProvider abstract interface
│       │   └── factory.py
│       └── notifications/
│           ├── base.py            # NotificationProvider abstract interface
│           └── factory.py
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/                  # Alembic migration files — never edit existing ones
│
├── tests/
│   ├── conftest.py                # Test fixtures (real DB, mock providers)
│   ├── unit/                      # Unit tests mirroring module structure
│   └── integration/               # Integration tests using real PostgreSQL + Redis
│
├── alembic.ini
├── pyproject.toml
├── .python-version
└── Dockerfile
```

---

## 6. Flutter App Structure (`apps/mobile/`)

```
apps/mobile/
├── lib/
│   ├── main.dart                  # App entry point
│   ├── app.dart                   # Root widget, router setup, provider scope
│   │
│   ├── core/
│   │   ├── router/                # GoRouter configuration and route definitions
│   │   ├── theme/                 # Material 3 theme (light, dark, typography)
│   │   ├── network/               # Dio client, interceptors, auth token injection
│   │   ├── storage/               # Drift database definition and DAOs
│   │   ├── error/                 # Error types, failure models, error widget
│   │   └── constants/             # App-wide constants (timeouts, keys, etc.)
│   │
│   ├── features/
│   │   └── {feature_name}/
│   │       ├── data/
│   │       │   ├── datasources/   # Remote (Dio) and local (Drift) data sources
│   │       │   ├── models/        # JSON-serializable data models (from/to API)
│   │       │   └── repositories/  # Repository implementations
│   │       ├── domain/
│   │       │   ├── entities/      # Pure Dart business objects — no JSON, no DB
│   │       │   ├── repositories/  # Repository abstract interfaces
│   │       │   └── usecases/      # Single-responsibility use case classes
│   │       └── presentation/
│   │           ├── providers/     # Riverpod providers (@riverpod annotated)
│   │           ├── screens/       # Full-page screen widgets
│   │           └── widgets/       # Feature-specific reusable widgets
│   │
│   └── shared/
│       ├── widgets/               # Reusable widgets used across features
│       └── utils/                 # Shared utility functions
│
├── test/
│   ├── unit/
│   ├── widget/
│   └── integration/
│
├── pubspec.yaml
└── Dockerfile
```

---

## 7. Coding Standards

### 7.1 Python (Backend)

- **Python version:** 3.12+
- **Line length:** 100 characters
- **Formatter:** Black (`--line-length 100`) — non-negotiable
- **Linter:** Ruff — zero violations allowed
- **Import order:** isort with Black-compatible profile
- **Type hints:** Required on every function signature and every class attribute. No `Any`
  unless absolutely unavoidable and commented with justification.
- **Async:** `async def` for all route handlers, service methods, repository methods, and
  anything that performs I/O.
- **Pydantic:** Always `model_config = ConfigDict(...)` (v2). Never `class Config`.
- **SQLAlchemy:** Always `Mapped[type]` with `mapped_column()` (2.0 style). Never old `Column()`.
- **Config access:** Always use `app.config.settings` (Pydantic BaseSettings). Never
  `os.environ` or `os.getenv` in application code.
- **Exceptions:** Always define module-specific exception classes in `exceptions.py`. Never
  raise bare `Exception`. Never use `except Exception` without re-raising or logging.
- **Logging:** Use Python's standard `logging` module with structured JSON output. Never `print()`.
- **Secrets:** Never hardcode credentials, keys, or tokens. Always reference via config.

### 7.2 Dart / Flutter (Mobile)

- **Dart SDK:** Stable channel, latest stable
- **Line length:** 100 characters
- **Formatter:** `dart format --line-length 100` — non-negotiable
- **Analyzer:** `dart analyze` — zero warnings or errors allowed on every commit
- **State management:** Riverpod with `@riverpod` annotation and `build_runner` code generation.
  Never raw `setState` for business-level state.
- **Navigation:** GoRouter exclusively. Never `Navigator.push` for main navigation flows.
  Modals are acceptable with `showModalBottomSheet` / `showDialog`.
- **HTTP:** All API calls go through the Dio client in `core/network/`. No raw `http` package.
- **Local data:** All SQLite operations go through Drift DAOs.
- **Null safety:** Strict null safety. Avoid `!` (bang operator) unless the non-null state is
  guaranteed by construction. Add a comment explaining why when `!` is genuinely necessary.
- **Widgets:** Prefer `ConsumerWidget` over `StatefulWidget` when Riverpod state is needed.
  Prefer `const` constructors wherever possible.
- **No business logic in widgets.** Widgets display state and dispatch events. They do not
  calculate, transform data, or make decisions.

---

## 8. Naming Conventions

### Python

| Item | Convention | Example |
|---|---|---|
| Module files | `snake_case.py` | `trip_service.py` |
| Classes | `PascalCase` | `TripService`, `TripRepository` |
| Functions / methods | `snake_case` | `get_trip_by_id`, `create_trip` |
| Variables | `snake_case` | `trip_id`, `user_email` |
| Constants | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_PAGE_SIZE` |
| Pydantic request models | `PascalCase + Request` | `TripCreateRequest`, `TripUpdateRequest` |
| Pydantic response models | `PascalCase + Response` | `TripResponse`, `TripListResponse` |
| SQLAlchemy models | `PascalCase` (singular) | `Trip`, `User`, `Destination` |
| Exception classes | `PascalCase + Error` | `TripNotFoundError`, `InvalidTokenError` |
| Repository classes | `PascalCase + Repository` | `TripRepository` |
| Service classes | `PascalCase + Service` | `TripService`, `AIService` |
| Test files | `test_{name}.py` | `test_trip_service.py` |

### Dart / Flutter

| Item | Convention | Example |
|---|---|---|
| Files | `snake_case.dart` | `trip_card.dart`, `trip_service.dart` |
| Classes | `PascalCase` | `TripCard`, `TripRepository` |
| Variables / fields | `camelCase` | `tripTitle`, `userId` |
| Constants | `camelCase` with `const` | `const maxRetries = 3` |
| Providers | `camelCase + Provider` | `tripListProvider`, `currentUserProvider` |
| Notifiers | `PascalCase + Notifier` | `TripListNotifier` |
| Screens | `PascalCase + Screen` | `TripDetailScreen`, `HomeScreen` |
| Widgets | `PascalCase + Widget` (optional suffix) | `TripCard`, `TripCardWidget` |
| Entities | `PascalCase` (singular) | `Trip`, `User`, `Destination` |
| Use cases | `PascalCase + UseCase` | `GetTripsUseCase`, `CreateTripUseCase` |

---

## 9. API Design Rules

All API behavior must conform to these rules. No exceptions without an ADR.

- All routes are prefixed `/api/v1/`. This prefix is set at the router registration level.
- Route naming: plural nouns, kebab-case. Example: `/api/v1/trips`, `/api/v1/trip-plans`.
- HTTP methods: GET (read), POST (create), PUT (full replace), PATCH (partial update),
  DELETE (remove).
- Every endpoint has an explicit Pydantic **request model** and **response model**.
  Raw dicts are never returned from endpoints.
- Errors use **RFC 7807 Problem Details** format: `type`, `title`, `status`, `detail`, `instance`.
- Collections use **cursor-based pagination**: `cursor`, `limit`, `next_cursor` in response.
- All endpoints require authentication by default. Public endpoints are explicitly annotated.
- File uploads are processed by the storage abstraction — never stored on the API server.
- Rate limiting is applied to all public endpoints and all AI-backed endpoints.

---

## 10. Database Rules

- Every schema change requires a **new Alembic migration**. Never edit an existing migration file.
- Never use `Base.metadata.create_all()` or `drop_all()` in production code. Only in test setup.
- Every **geometry column** (PostGIS) requires a **GiST index** created in the same migration.
- Every user-facing entity requires a `deleted_at TIMESTAMP WITH TIME ZONE` column (soft delete).
- Every table requires `created_at` and `updated_at` timestamp columns with timezone.
- All `updated_at` columns must auto-update via a database trigger or SQLAlchemy event.
- Foreign keys must declare explicit `ON DELETE` behavior (`CASCADE`, `SET NULL`, `RESTRICT`).
- Connection pooling must be explicitly configured in `database.py`:
  - `pool_size`: number of persistent connections
  - `max_overflow`: burst capacity above pool_size
  - `pool_timeout`: seconds to wait for a connection before raising an error
- Raw SQL is only acceptable for PostGIS spatial queries where the ORM cannot express the query.
  All raw SQL must be parameterized — never string-formatted.

---

## 11. Authentication and Security Rules

- **JWT access tokens:** Short-lived — 15 minutes maximum.
- **Refresh tokens:** 7-day expiry, stored in PostgreSQL, support explicit revocation.
- **Token revocation:** Redis-backed blacklist. On logout or suspicious activity, the token
  family is invalidated in Redis immediately.
- **Refresh token rotation:** Every `/auth/refresh` call issues a new refresh token and
  invalidates the previous one. Reuse of a superseded refresh token invalidates the entire
  family (stolen token detection).
- **Mobile token storage:** Flutter Secure Storage (backed by Android Keystore / iOS Secure
  Enclave). Never `SharedPreferences`. Never Drift (unencrypted SQLite).
- **Input validation:** Pydantic validates all user input at the API boundary. Never trust
  client-supplied data.
- **AI prompt injection prevention:** User-supplied text is always passed as data values in
  prompt templates. Never interpolated directly into instruction text.
- **CORS:** Explicitly configured with allowed origins per environment. Never `*` in production.
- **Secrets:** Managed via environment variables. Never committed to the repository.
- **Google Maps API keys:** Two separate keys — one for the mobile app (restricted by
  fingerprint/bundle ID), one for server-side Maps API calls (restricted to server IP, never
  shipped to the client).

---

## 12. Service Abstraction Layer

All external services must be accessed through an abstract interface. This is mandatory.

### Pattern

```
app/services/{service_type}/
├── base.py         # Abstract class or Protocol defining the interface
├── {provider}.py   # Concrete implementation (e.g., openai.py, mock.py)
└── factory.py      # Reads config and returns the correct implementation
```

### AI Service Contract (example)

The AI service interface must expose only domain-level operations. Provider-specific concepts
(token counts, model names, API versions) must not appear in the interface signature.

```
AIProvider interface methods (example):
- generate_trip_plan(destinations, preferences, constraints) -> TripPlan
- summarize_destination(destination_name, context) -> str
- suggest_activities(trip_context) -> list[ActivitySuggestion]
```

### Required Providers

| Service | Interface | Mock Required |
|---|---|---|
| AI | `AIProvider` | Yes — `MockAIProvider` |
| Maps | `MapsProvider` | Yes — `MockMapsProvider` |
| Storage | `StorageProvider` | Yes — `MockStorageProvider` |
| Email | `EmailProvider` | Yes — `MockEmailProvider` |
| Weather | `WeatherProvider` | No — Open-Meteo is free, use directly in tests |
| Notifications | `NotificationProvider` | Yes — `MockNotificationProvider` |

### Rule

No feature module (`app/modules/*`) may import from any external provider package directly.
All imports of external capabilities go through `app/services/`.

---

## 13. Testing Requirements

### Backend

- **Unit tests** for every service method and repository method.
- **Integration tests** use a real PostgreSQL + Redis instance (Docker in CI).
  No mocking the database in integration tests — this is a firm rule.
- The AI provider is always mocked with `MockAIProvider` in non-AI-specific tests.
- All tests live in `apps/api/tests/` and mirror the module structure.
- Test files are named `test_{module_name}.py`.
- CI requires all tests to pass before a PR can be merged.
- Coverage target: 80% minimum for service and repository layers.

### Flutter

- **Widget tests** for every screen widget.
- **Unit tests** for every use case and repository implementation.
- **Integration tests** for critical user flows using `flutter_test`.
- Mock providers are injected via Riverpod overrides in tests.

---

## 14. Task Execution Process

When given an engineering task:

1. **Read the task specification** in `docs/tasks/` before writing any code.
2. **Read CLAUDE.md** (this file) completely if not already done.
3. **Read relevant ADRs** in `docs/adr/` for any decision that affects your task.
4. **Identify the affected modules** and confirm the change scope before starting.
5. **Implement within the defined module structure.** Never create new top-level directories.
6. **Write tests first or alongside implementation** — never defer tests to "later".
7. **Run the Definition of Done checklist** (Section 16) before declaring a task complete.
8. **Confirm with the user** before making changes that cross module boundaries.

---

## 15. Rules Claude Must Follow

1. **Always read this file completely** before starting any implementation task.
2. **Always read the task specification** in `docs/tasks/` before writing code.
3. **Always implement within the defined module structure.** Do not create new directories
   that are not in the structure defined in Sections 5 and 6.
4. **Always use the service abstraction layer** for any external service call.
5. **Always write Pydantic models** for every API request and response body.
6. **Always use type hints** on every Python function signature and class attribute.
7. **Always use `async def`** for all route handlers, services, and repository methods.
8. **Always add a GiST index** to every PostGIS geometry column in the same migration.
9. **Always create a new Alembic migration** for every schema change.
10. **Always use `Mapped[]` and `mapped_column()`** in SQLAlchemy models (2.0 style).
11. **Always use `model_config = ConfigDict()`** in Pydantic models (v2 style).
12. **Always use Riverpod with `@riverpod` code generation** in Flutter.
13. **Always use GoRouter** for navigation in Flutter.
14. **Always prefix API routes with `/api/v1/`.**
15. **Always validate the Definition of Done** (Section 16) before completing a task.
16. **Always follow naming conventions** in Section 8.
17. **Always confirm with the user** before changes that span more than one feature module.

---

## 16. Rules Claude Must Never Do

1. **Never add business logic to Flutter.** The app calls the API and displays results.
2. **Never import external provider SDKs** (openai, anthropic, googlemaps, boto3, etc.)
   directly in any feature module. Only through `app/services/`.
3. **Never use `os.environ` directly** in application code. Use the Pydantic settings object.
4. **Never hardcode secrets, API keys, credentials, or tokens** in any file.
5. **Never modify an existing Alembic migration file.** Always create a new one.
6. **Never use `Column()` or old SQLAlchemy 1.x ORM patterns.**
7. **Never use `class Config` in Pydantic models.** Use `model_config = ConfigDict(...)`.
8. **Never store authentication tokens** in Flutter `SharedPreferences` or unencrypted storage.
9. **Never commit `.env` files.** Only `.env.example` belongs in the repository.
10. **Never use `Navigator.push`** for main-flow navigation in Flutter.
11. **Never generate factual travel data via AI** (hotel names, real addresses, prices,
    operating hours, ratings). AI generates structure and suggestions; factual data comes from
    verified external sources or user input.
12. **Never drop or truncate database tables** outside of isolated test teardown.
13. **Never skip tests.** Every feature and bug fix requires tests.
14. **Never create a new top-level directory** without documented architectural approval.
15. **Never use `print()` in Python.** Use the `logging` module with structured output.
16. **Never use `!` (bang) in Dart** unless the non-null invariant is provably guaranteed
    by construction, with a comment explaining why.
17. **Never return raw SQLAlchemy model objects from API endpoints.** Always convert to
    Pydantic response models first.
18. **Never use `except Exception` without re-raising or explicit structured logging.**

---

## 17. Definition of Done

A task is **only complete** when every item in this checklist is satisfied:

### Code Quality
- [ ] Implementation matches the task specification in `docs/tasks/`
- [ ] All functions and class attributes have type hints (Python) or type annotations (Dart)
- [ ] `ruff check .` passes with zero violations (Python)
- [ ] `black --check .` passes with no changes (Python)
- [ ] `dart analyze` passes with zero issues (Flutter)
- [ ] `dart format --check .` passes with no changes (Flutter)

### Architecture
- [ ] No business logic added to Flutter
- [ ] All external service calls go through the abstraction layer
- [ ] Module boundaries respected — no circular imports
- [ ] Naming conventions followed (Section 8)

### Database (if schema changed)
- [ ] A new Alembic migration was created (existing migrations not modified)
- [ ] PostGIS geometry columns have GiST indexes in the migration
- [ ] Soft-delete column added for user-facing entities
- [ ] `created_at` and `updated_at` columns present

### API (if endpoints added/changed)
- [ ] All routes prefixed `/api/v1/`
- [ ] All endpoints have Pydantic request and response models
- [ ] Error responses follow RFC 7807 Problem Details format
- [ ] Authentication applied unless explicitly public

### Security
- [ ] No secrets or credentials present in any committed file
- [ ] No `os.environ` usage in application code
- [ ] User input validated at the API boundary
- [ ] Token storage uses Flutter Secure Storage on mobile

### Tests
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing (for DB/service interactions)
- [ ] AI provider mocked in non-AI-specific tests

### Documentation
- [ ] Pull request template fully completed
- [ ] ADR created if the task involves a significant architectural decision
- [ ] Task specification in `docs/tasks/` marked complete

---

## 18. Environment Variables

All configuration is managed through environment variables loaded via Pydantic `BaseSettings`
in `apps/api/app/config.py`. See `.env.example` in the repository root for the complete list
of required variables.

**Naming convention:** `SCREAMING_SNAKE_CASE`, grouped by service prefix.

**Local development:** `.env` file in the repository root (never committed).
**CI/CD:** GitHub Secrets injected as environment variables.
**Reference:** `.env.example` (committed, no real values).

---

## 19. Key Architectural Decisions

See `docs/adr/` for the full ADR log.

| Decision | Choice | Rationale |
|---|---|---|
| Backend deployment pattern | Modular Monolith | Avoids premature microservice complexity; clean module boundaries allow future extraction |
| Async task queue | ARQ | Async-native, Redis-backed, minimal overhead for FastAPI |
| Token revocation mechanism | Redis blacklist + refresh token rotation | Stateless JWT cannot revoke; rotation detects stolen tokens |
| AI integration | Provider abstraction layer | Zero vendor lock-in; `MockAIProvider` enables local development |
| Mobile state management | Riverpod (code generation) | Best-in-class DI and reactivity for Flutter; testable via overrides |
| Offline data layer | Drift (SQLite + type-safe) | Reactive streams, type-safety, Riverpod integration |
| API versioning | `/api/v1/` prefix | Allows non-breaking API evolution; enforced at router registration |
| Spatial data | PostGIS + GiST indexes | Industry standard; required for any geo-aware query |
| Soft deletes | `deleted_at` timestamp | Users expect data recovery; hard deletes are permanent and dangerous |

---

## 20. Questions and Escalation

If a task specification is unclear, **ask before implementing**. Do not guess at ambiguous
requirements. The cost of clarification is always lower than the cost of rework.

If a task appears to require violating any rule in this document, **stop and escalate**.
The rules in this document reflect deliberate architectural decisions. Violating them without
discussion creates technical debt that affects the entire system.
