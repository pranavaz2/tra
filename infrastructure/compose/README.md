# infrastructure/compose/ — Docker Compose Files

This folder contains **Docker Compose files** for orchestrating Travix AI services
across different environments.

---

## Purpose

Docker Compose files define the multi-service environment needed to run Travix AI locally
and in CI. Different Compose files target different scenarios — local development requires
hot reload and volume mounts; CI requires fast startup and no persistent state.

---

## Files

| File | Environment | Purpose |
|---|---|---|
| [`docker-compose.yml`](docker-compose.yml) | Base (all environments) | Canonical service definitions, networks, volumes, health checks |
| [`docker-compose.override.yml`](docker-compose.override.yml) | Local development | Bind mounts, exposed ports, dev image build, env_file |
| [`docker-compose.prod.yml`](docker-compose.prod.yml) | Production | Production image, no host port exposure for DB/Redis, restart:always |

Compose files use the **override pattern**:
- `docker-compose.yml` defines canonical service configurations — never used standalone
- `docker-compose.override.yml` is automatically merged for local dev when both files are present
- For production: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
- `make docker-up` handles the file references automatically

---

## Services Managed

| Service | Image | Purpose |
|---|---|---|
| `postgres` | `postgis/postgis:16-3.4` | PostgreSQL 16 + PostGIS 3.4 |
| `redis` | `redis:7-alpine` | Cache, ARQ task queue, token revocation (AOF enabled) |
| `api` | Built from `apps/api/Dockerfile.dev` (dev) or `$API_IMAGE` (prod) | FastAPI backend |

---

## Port Assignments (local development)

| Service | Port | Access URL |
|---|---|---|
| FastAPI API | `8000` | `http://localhost:8000` |
| FastAPI docs | `8000` | `http://localhost:8000/docs` |
| PostgreSQL | `5432` | `postgresql://localhost:5432/travix_db` |
| Redis | `6379` | `redis://localhost:6379` |

---

## Usage

```bash
# Start all services (PostgreSQL + Redis)
make docker-up

# Stop all services
make docker-down

# View logs
make docker-logs

# Or use docker compose directly
docker compose -f infrastructure/compose/docker-compose.yml up -d
```

---

## Status

- [x] `docker-compose.yml` — base configuration
- [x] `docker-compose.override.yml` — local development overrides
- [x] `docker-compose.prod.yml` — production overrides
