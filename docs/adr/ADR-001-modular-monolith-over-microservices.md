# ADR-001: Modular Monolith Over Microservices

| Field       | Value                        |
|-------------|------------------------------|
| **Status**  | Accepted                     |
| **Date**    | 2026-06-26                   |
| **Deciders**| Engineering Team             |

---

## Context

Travix AI is a new platform entering active development. We need to choose a deployment
architecture that can handle the current team size and feature scope while remaining
maintainable and extensible as the product grows.

The two primary candidates are:

1. **Microservices** — each feature (auth, trips, weather, AI) is an independently deployable
   service with its own database and deployment pipeline.
2. **Modular Monolith** — a single deployable unit with enforced internal module boundaries,
   organized by feature.

## Decision

We will build the backend as a **Modular Monolith**.

The backend is a single FastAPI application (`apps/api/`) divided into isolated feature modules
under `app/modules/`. Module boundaries are enforced through Python package structure and
import discipline. No feature module may import from another feature module's internal code —
cross-module communication happens only through shared domain interfaces.

## Rationale

### Against microservices at this stage

- **Team size** — the engineering team is small. Microservices multiply operational surface
  area: separate CI pipelines, deployment scripts, container registries, health monitoring,
  and inter-service networking for every service. The overhead is disproportionate.
- **Distributed systems complexity** — microservices introduce network partitions, eventual
  consistency, distributed tracing, and service discovery as day-one concerns. These are
  problems worth solving at scale, not while building the initial product.
- **Premature optimization** — we don't yet have enough data about where the bottlenecks will
  be. Splitting services before traffic patterns emerge often results in splitting along the
  wrong boundaries.
- **Database per service** — microservices require either isolated databases (complex data
  ownership and joins) or a shared database (defeating the isolation purpose). PostGIS spatial
  queries that cross feature boundaries are much simpler in a single database.

### For modular monolith

- **Clean boundaries without network overhead** — modules are isolated by Python package
  structure. Import violations are caught by linters and code review. Refactoring a module
  boundary is a local change, not a service re-architecture.
- **Extraction path** — a well-structured modular monolith is the prerequisite for successful
  microservice extraction. If a module needs to become a service, it already has a clean
  interface, a defined data boundary, and no circular dependencies. The extraction is
  mechanical, not a rewrite.
- **Single deployment unit** — one container, one CI pipeline, one deployment. The operational
  model is simple until the product demands otherwise.
- **Shared infrastructure** — auth middleware, request ID propagation, structured logging,
  database sessions, and Redis connections are defined once in `app/core/` and used by all
  modules without duplication.
- **PostGIS spatial queries** — geo-aware queries often join across feature domains
  (e.g., trips + destinations + user location). A single database makes these joins trivial.

## Consequences

### Positive
- Simpler local development — one `docker compose up` starts the entire backend.
- Simpler CI — one test suite, one lint run, one Docker build.
- Shared database transactions across features where needed.
- No distributed tracing or service mesh required.

### Negative / Mitigations
- **Shared process** — a crash in one module can affect all modules. Mitigation: strict error
  handling at module boundaries; use the ARQ task queue to isolate slow/unreliable operations.
- **Shared database** — a slow query in one module can impact others. Mitigation: connection
  pooling, per-module async repository pattern, PostGIS GiST indexes on all geometry columns.
- **Horizontal scaling couples services** — scaling the AI-heavy endpoints requires scaling
  the entire container. Mitigation: AI and heavy operations are offloaded to ARQ workers
  (separate containers). The API container remains lightweight and stateless.
- **Import discipline** — without a compiler enforcing boundaries, developers can accidentally
  bypass module isolation. Mitigation: Ruff import rules, code review, and a documented rule
  in CLAUDE.md that is checked in the Definition of Done.

## Review Trigger

Re-evaluate this decision when any of the following are true:

- A single module has > 5x the traffic of the rest of the application and cannot be optimized
  independently within the monolith.
- The engineering team exceeds 15 people and feature teams are blocked waiting on each other's
  deployments.
- A module requires a different technology stack (e.g., a real-time service requiring Node.js).
