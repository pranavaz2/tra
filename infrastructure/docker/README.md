# infrastructure/docker/ — Dockerfiles

This folder contains **Dockerfiles** for all Travix AI services.

---

## Purpose

Each service that runs in a container has its own Dockerfile here. Centralizing Dockerfiles
in `infrastructure/docker/` (rather than scattering them inside each app directory) makes
the infrastructure layer explicit and easy to find.

The Dockerfiles here are used by Docker Compose files in `infrastructure/compose/` and
by GitHub Actions CI/CD workflows.

---

## Expected Files

| File | Service | Description |
|---|---|---|
| `Dockerfile.api` | FastAPI backend | Production image for `apps/api` |
| `Dockerfile.api.dev` | FastAPI backend | Development image with hot reload |
| `Dockerfile.worker` | ARQ task worker | Worker process image |
| `Dockerfile.mobile` | Flutter build | CI image for building Flutter APK/IPA |

---

## Image Design Principles

- **Multi-stage builds:** Production images use multi-stage builds to minimize final image size.
  Build dependencies are not present in the production image.
- **Non-root user:** Production images run as a non-root user for security.
- **Pinned base images:** Base image versions are pinned to exact digests or specific patch
  versions. Never use `:latest`.
- **Layer caching:** Dependencies are installed in a separate layer from application code
  to maximize cache efficiency.
- **Health checks:** All service images define a `HEALTHCHECK` instruction.

---

## Naming Convention

```
Dockerfile.{service}[.{variant}]
```

| Variant | Purpose |
|---|---|
| (no variant) | Production image |
| `.dev` | Development image (hot reload, debug tools) |
| `.ci` | CI-specific image (test runners, lint tools) |

---

## Current Dockerfiles

Dockerfiles live alongside the source code they build, not in this directory. This is the
canonical lookup table:

| Service | Production | Development | Location |
|---------|-----------|-------------|----------|
| FastAPI API | `Dockerfile` | `Dockerfile.dev` | `apps/api/` |
| Flutter mobile | — | — | `apps/mobile/` _(future)_ |
| ARQ worker | Shares API image | Shares API dev image | — |

The ARQ task worker uses the same Docker image as the API. In production, the worker
container is started with `CMD ["arq", "app.worker.WorkerSettings"]` instead of gunicorn.
No separate Dockerfile is needed.

## Status

- [x] `apps/api/Dockerfile` — production multi-stage image
- [x] `apps/api/Dockerfile.dev` — development image with hot-reload
- [ ] `apps/mobile/Dockerfile` — Flutter CI build image _(future task)_
