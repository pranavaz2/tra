# Travix AI

An AI-powered travel planning platform built for the modern traveler.

---

## Overview

Travix AI enables users to plan, organize, and experience travel through intelligent itinerary
generation, real-time weather integration, and interactive maps — all powered by a replaceable
AI provider abstraction layer built for scale, security, and longevity.

---

## Architecture Overview

Travix AI is a **Modular Monolith** following **Clean Architecture**, **Vertical Slice
Architecture**, and **Domain-Driven Design** principles.

```
┌─────────────────────────────────────┐
│      Flutter App (Presentation)     │
│  Riverpod · GoRouter · Drift · Dio  │
└────────────────┬────────────────────┘
                 │ HTTPS / REST
┌────────────────▼────────────────────┐
│    FastAPI (Business Logic + API)   │
│  SQLAlchemy 2.0 · Pydantic v2 · ARQ │
└──────┬────────────────┬─────────────┘
       │                │
┌──────▼──────┐  ┌──────▼──────┐
│  PostgreSQL  │  │    Redis    │
│  + PostGIS   │  │  Cache/Queue│
└─────────────┘  └─────────────┘
```

**Key architectural rules:**

- The Flutter app is **presentation only**. No business logic lives in the client.
- The FastAPI backend **owns all business logic**, validation, and AI orchestration.
- Every external service (AI, Maps, Storage, Email, Weather) is accessed through an **internal
  abstraction layer**. No vendor lock-in.
- The AI provider is **fully replaceable** via configuration.

---

## Technology Stack

### Mobile (`apps/mobile/`)

| Technology | Purpose |
|---|---|
| Flutter | Cross-platform mobile framework |
| Riverpod | State management (code generation pattern) |
| GoRouter | Declarative navigation |
| Dio | HTTP client with interceptors |
| Drift | Reactive local SQLite ORM (offline support) |
| Material 3 | Design system |

### Backend (`apps/api/`)

| Technology | Purpose |
|---|---|
| FastAPI | Async Python web framework |
| SQLAlchemy 2.0 (async) | ORM with `AsyncSession` and `Mapped[]` |
| Alembic | Database migrations |
| PostgreSQL + PostGIS | Primary database with spatial support |
| Pydantic v2 | Data validation and serialization |
| ARQ | Async task queue (backed by Redis) |

### Infrastructure

| Technology | Purpose |
|---|---|
| Docker | Containerization |
| Docker Compose | Local development orchestration |
| Redis | Caching, task queue broker, token revocation |
| GitHub Actions | CI/CD |

### External Services (all behind internal abstractions)

| Service | Purpose | Status |
|---|---|---|
| Google Maps Platform | Maps, geocoding, places | Active |
| Open-Meteo | Weather data | Active |
| Firebase Cloud Messaging | Push notifications | Future |
| Resend | Transactional email | Future |
| Cloudflare R2 | Object storage | Future |

---

## Repository Structure

```
travix-ai/
├── apps/
│   ├── mobile/          # Flutter application
│   └── api/             # FastAPI application
├── packages/            # Shared internal packages
├── docs/
│   ├── product-bible/   # Product requirements and vision
│   ├── adr/             # Architecture Decision Records
│   ├── architecture/    # System architecture documentation
│   ├── api/             # API contracts and documentation
│   ├── decisions/       # Engineering decisions (non-ADR)
│   ├── tasks/           # Engineering task specifications
│   └── diagrams/        # System and flow diagrams
├── infrastructure/
│   ├── docker/          # Dockerfiles
│   ├── compose/         # Docker Compose files
│   └── scripts/         # Developer utility scripts
└── .github/             # GitHub Actions and repository templates
```

---

## Local Development Setup

> **Prerequisites:** Docker, Docker Compose, Flutter SDK, Python 3.12+, Make

```bash
# Clone the repository
git clone https://github.com/travix-ai/travix-ai.git
cd travix-ai

# Copy environment variables
cp .env.example .env
# Edit .env with your local values

# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Start infrastructure services
make docker-up

# Run database migrations
make migrate

# Start the API
make run-api

# Start the mobile app (separate terminal)
make run-mobile
```

> See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development workflow.

---

## Development Workflow

1. Read the relevant task specification in [`docs/tasks/`](docs/tasks/)
2. Create a branch following the naming convention in [CONTRIBUTING.md](CONTRIBUTING.md)
3. Implement within the defined module structure
4. Verify all items in the Definition of Done ([CLAUDE.md](CLAUDE.md))
5. Submit a pull request using the provided template

---

## Documentation

| Document | Purpose |
|---|---|
| [CLAUDE.md](CLAUDE.md) | Authoritative engineering guide and AI collaboration rules |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development workflow, standards, and branching conventions |
| [docs/adr/](docs/adr/) | Architecture Decision Records |
| [docs/architecture/](docs/architecture/) | System architecture documentation |
| [docs/api/](docs/api/) | API contract documentation |
| [docs/tasks/](docs/tasks/) | Engineering task specifications |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## License

MIT License — see [LICENSE](LICENSE).
