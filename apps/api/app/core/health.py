"""
Travix AI — Health Check Endpoints

Implements three health endpoints with distinct semantics:

  GET /health   Liveness   — Is the process running?
                            No I/O. Returns 200 immediately.
                            Called every ~5s by container orchestrators.

  GET /ready    Readiness  — Can this instance accept traffic?
                            Checks DB + Redis. Returns 503 if any dependency
                            is unavailable. Used by load balancers.

  GET /live     Deep live  — Is this instance healthy under load?
                            Placeholder for future memory/queue checks.
                            Returns 200 until specific thresholds are defined.

These endpoints are infrastructure-only. They do not check business-layer
health (e.g., AI provider availability) and do not require authentication.
They are excluded from rate limiting and access logging at the middleware layer.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.database import check_database_health
from app.redis import check_redis_health

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Infrastructure"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class CheckResult(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["alive", "healthy", "degraded", "unhealthy"]
    version: str
    environment: str
    timestamp: str
    checks: Optional[dict[str, CheckResult]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Returns 200 immediately if the process is running. No I/O performed.",
)
async def health() -> HealthResponse:
    from app.config import get_settings

    s = get_settings()
    return HealthResponse(
        status="alive",
        version=s.app_version,
        environment=s.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness check",
    description=(
        "Returns 200 when all critical dependencies (database, Redis) are available. "
        "Returns 503 when any dependency is unreachable. "
        "Used by load balancers to gate traffic routing."
    ),
)
async def ready(response: Response) -> HealthResponse:
    from app.config import get_settings

    s = get_settings()

    # Run checks concurrently — both checks run in parallel, not sequentially
    db_result, redis_result = await asyncio.gather(
        check_database_health(),
        check_redis_health(),
        return_exceptions=True,
    )

    # Exceptions from gather are returned as values, not re-raised
    if isinstance(db_result, Exception):
        db_result = {"status": "unhealthy", "error": type(db_result).__name__}
    if isinstance(redis_result, Exception):
        redis_result = {"status": "unhealthy", "error": type(redis_result).__name__}

    all_healthy = (
        db_result.get("status") == "healthy"  # type: ignore[union-attr]
        and redis_result.get("status") == "healthy"  # type: ignore[union-attr]
    )

    if not all_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning(
            "Readiness check failed",
            extra={"database": db_result, "redis": redis_result},
        )

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        version=s.app_version,
        environment=s.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        checks={
            "database": CheckResult(**db_result),  # type: ignore[arg-type]
            "redis": CheckResult(**redis_result),  # type: ignore[arg-type]
        },
    )


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Deep liveness check",
    description=(
        "Returns 200 when the instance is healthy under load. "
        "Future: will check memory usage, queue depth, and error rate thresholds."
    ),
)
async def live() -> HealthResponse:
    from app.config import get_settings

    s = get_settings()
    # TODO: Add queue depth check (ARQ), memory threshold check
    return HealthResponse(
        status="healthy",
        version=s.app_version,
        environment=s.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
