"""
Travix AI — Redis Infrastructure

Provides:
  - Per-database Redis client factory (lazy-initialized)
  - Pre-configured clients for each logical Redis database
  - CacheBackend abstract interface
  - RedisCacheBackend concrete implementation
  - Redis health check for /ready endpoint

Redis database allocation:
  DB 0 → General API response cache
  DB 1 → ARQ task queue (managed by ARQ internally)
  DB 2 → JWT token revocation list (requires AOF persistence)
  DB 3 → Rate limit counters
  DB 4 → AI response cache (long TTL, expensive to regenerate)
  DB 5 → Session metadata (multi-step user flows)

Important: Redis DB 2 (token revocation) MUST run with AOF persistence
enabled. A restart that loses revocation data allows previously revoked
tokens to pass authentication until they expire naturally.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------


def _create_client(url: str, db: int) -> aioredis.Redis:
    """Create a Redis client for the given URL and logical database number."""
    return aioredis.from_url(
        url,
        db=db,
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        retry_on_timeout=True,
    )


# ---------------------------------------------------------------------------
# Lazy per-database singletons
# ---------------------------------------------------------------------------

_clients: dict[int, aioredis.Redis] = {}


def _get_client(db: int) -> aioredis.Redis:
    """
    Return the Redis client for the given logical database, creating it on
    first access. Lazy initialization ensures settings are available at
    call time regardless of import order.
    """
    if db not in _clients:
        from app.config import get_settings

        s = get_settings()
        _clients[db] = _create_client(s.redis_url, db)
    return _clients[db]


def get_cache_client() -> aioredis.Redis:
    from app.config import get_settings

    return _get_client(get_settings().redis_cache_db)


def get_token_revocation_client() -> aioredis.Redis:
    from app.config import get_settings

    return _get_client(get_settings().redis_token_revocation_db)


def get_rate_limit_client() -> aioredis.Redis:
    from app.config import get_settings

    return _get_client(get_settings().redis_rate_limit_db)


def get_ai_cache_client() -> aioredis.Redis:
    from app.config import get_settings

    return _get_client(get_settings().redis_ai_cache_db)


def get_session_client() -> aioredis.Redis:
    from app.config import get_settings

    return _get_client(get_settings().redis_session_db)


# ---------------------------------------------------------------------------
# Cache abstraction
# ---------------------------------------------------------------------------


class CacheBackend(ABC):
    """
    Abstract interface for cache operations.

    Feature modules must program to this interface, not to Redis directly.
    This enables mock implementations in tests and alternative backends.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Retrieve a cached value by key. Returns None on cache miss."""
        ...

    @abstractmethod
    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """
        Store a value with an optional TTL in seconds.
        If ttl is None, use the backend default TTL.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a key from the cache. No-op if key does not exist."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Return True if the key exists in the cache."""
        ...

    @abstractmethod
    async def ping(self) -> bool:
        """Return True if the backend is reachable."""
        ...


class RedisCacheBackend(CacheBackend):
    """
    Redis implementation of CacheBackend.

    Key format convention: {namespace}:v{version}:{identifier}
    Example: weather:v1:london:2025-01-15

    The :v{version}: segment enables cache invalidation by version bump
    without flushing the entire cache database.
    """

    def __init__(self, client: aioredis.Redis, default_ttl: int = 300) -> None:
        self._client = client
        self._default_ttl = default_ttl

    async def get(self, key: str) -> Optional[str]:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        await self._client.set(key, value, ex=ttl if ttl is not None else self._default_ttl)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def ping(self) -> bool:
        try:
            return bool(await self._client.ping())
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------


async def close_redis() -> None:
    """
    Close all open Redis connections. Call during application shutdown.

    Registered automatically in app.main lifespan context manager.
    """
    for db, client in list(_clients.items()):
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning("Error closing Redis client for db=%d: %s", db, exc)
    _clients.clear()
    logger.debug("Redis connections closed")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


async def check_redis_health() -> dict[str, object]:
    """
    Ping Redis to verify connectivity.

    Returns a dict compatible with the HealthResponse.checks schema.
    Never raises — failures are captured and returned as unhealthy status.
    """
    start = time.monotonic()
    try:
        client = get_cache_client()
        await client.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return {"status": "healthy", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        logger.error("Redis health check failed: %s", exc)
        return {
            "status": "unhealthy",
            "latency_ms": latency_ms,
            "error": type(exc).__name__,
        }
