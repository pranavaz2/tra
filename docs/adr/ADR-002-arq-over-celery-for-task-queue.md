# ADR-002: ARQ Over Celery for the Async Task Queue

| Field       | Value                        |
|-------------|------------------------------|
| **Status**  | Accepted                     |
| **Date**    | 2026-06-26                   |
| **Deciders**| Engineering Team             |

---

## Context

Travix AI offloads slow and unreliable operations — AI itinerary generation, external API
calls, email delivery, push notifications — to an async task queue. The API receives a request,
enqueues a job, and responds immediately with a job ID. The client polls or receives a push
notification when the job completes.

We need to choose a task queue library. The main candidates evaluated were:

1. **Celery** — the dominant Python task queue. Supports multiple brokers (Redis, RabbitMQ,
   SQS). Large ecosystem.
2. **ARQ** — a lightweight async task queue built specifically for asyncio. Redis-backed only.
3. **RQ (Redis Queue)** — synchronous Redis-backed task queue.

## Decision

We will use **ARQ** as the async task queue, backed by Redis.

## Rationale

### ARQ is async-native

Travix AI's entire backend is `async`/`await`. Every route handler, service method, and
repository method is `async def`. ARQ worker functions are also `async def`, which means:

- AI provider calls (`await ai_provider.generate_trip_plan(...)`) run natively in the worker.
- Database sessions are `AsyncSession` — compatible with the same session factory used in the API.
- Redis connections are `aioredis` — reused from the existing Redis infrastructure.
- No thread-pool executors or `asyncio.run()` wrappers are needed to call async code from tasks.

Celery workers are synchronous by default. Running async task code from Celery requires
`gevent`/`eventlet` monkey-patching or a `loop.run_until_complete()` wrapper — both are
fragile and add a compatibility surface that grows with every library upgrade.

### Shared Redis infrastructure

Redis is already a hard dependency for token revocation and response caching. Adding ARQ
requires no new infrastructure — the task queue runs on a dedicated logical database (DB 1)
within the same Redis instance. This eliminates the need for RabbitMQ or SQS as a broker.

### Minimal API surface

ARQ's API is small and direct:

```python
# Enqueue
await arq_pool.enqueue_job("generate_itinerary", trip_id=trip_id)

# Worker definition
async def generate_itinerary(ctx: dict, trip_id: UUID) -> None:
    db: AsyncSession = ctx["db"]
    ai: AIProvider = ctx["ai"]
    ...
```

There is no `@task` decorator registry, no routing configuration, no result backend setup
beyond Redis. The entire task worker fits in a single `worker.py` file per module.

### Sufficient feature set

ARQ provides what Travix AI needs:

- Deferred execution and scheduling
- Job result storage with TTL (Redis-backed)
- Worker concurrency control
- Job retry with exponential backoff
- Health check via `arq.check_health()`

It does not provide complex routing topologies, priority queues, or canvas workflows. Those
are not requirements for this system.

## Consequences

### Positive
- No new infrastructure dependency — reuses Redis.
- Worker code is idiomatic `async def` with no compatibility shims.
- Shared `AsyncSession` factory and AI provider between API and workers.
- Simple deployment — workers are the same Docker image as the API, different CMD.

### Negative / Mitigations
- **Redis-only broker** — ARQ does not support RabbitMQ or SQS. Mitigation: Redis is
  already a required dependency. If Redis becomes unavailable, the task queue is unavailable
  regardless of broker — the failure domain is the same.
- **No dead-letter queue** — failed jobs are retried per policy, then dropped. Mitigation:
  failed jobs are logged with `structured JSON` before being discarded. An alert fires when
  the job failure rate exceeds a threshold. A dead-letter mechanism can be added with a
  custom `on_job_abort` hook if needed.
- **Smaller ecosystem** — fewer plugins and integrations than Celery. Mitigation: Travix AI
  does not rely on Celery-specific integrations (Django ORM, SQLAlchemy sessions in Celery
  work differently from ARQ's `ctx` pattern).
- **Limited scheduling** — ARQ's cron is basic. Mitigation: complex scheduling is handled
  externally (GitHub Actions cron, cloud scheduler) calling API endpoints. ARQ handles
  on-demand and deferred jobs only.

## Review Trigger

Re-evaluate this decision if:

- A task requires a broker feature ARQ cannot support (e.g., fanout, topic exchange,
  priority lanes with strict ordering guarantees).
- Redis becomes unavailable as a platform dependency (e.g., replaced by a managed broker
  service with no Redis compatibility layer).
- Task volume exceeds ARQ's single-process concurrency limits and horizontal scaling of
  workers does not resolve the bottleneck.
