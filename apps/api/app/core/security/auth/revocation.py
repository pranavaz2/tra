"""
Token revocation checker implementations.

NullTokenRevocationChecker — placeholder for TASK-2.12 (Redis JTI blacklist).
Reports every token as non-revoked. Safe to use in development and test environments
where Redis is unavailable or where logout has not yet been implemented.

Production replacement (TASK-2.12):
  class RedisTokenRevocationChecker:
      def __init__(self, redis: Redis) -> None:
          self._redis = redis

      async def is_revoked(self, jti: str) -> bool:
          return await self._redis.exists(f"revoked:jti:{jti}") > 0

      async def revoke(self, jti: str, expires_at: datetime) -> None:
          ttl = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
          await self._redis.setex(f"revoked:jti:{jti}", ttl, "1")

  Redis DB: redis_token_revocation_db (DB 2, AOF persistence required)
  Key format: revoked:jti:{jti}
  TTL: remaining token lifetime (exp - now), minimum 1 second

Revocation events (wired in TASK-2.12+):
  POST /auth/logout          → revoke current access token JTI
  POST /auth/logout-all      → revoke all outstanding JTIs for the user
  Account deactivation       → revoke all outstanding JTIs for the user
  Refresh token reuse        → revoke all outstanding JTIs (stolen token)
"""

from __future__ import annotations

from datetime import datetime


class NullTokenRevocationChecker:
    """
    No-op placeholder — always reports tokens as non-revoked.

    Used as the default injection until TASK-2.12 adds the Redis implementation.
    Swap by overriding get_token_revocation_checker() in dependency_overrides
    or by switching the factory function in dependencies.py.
    """

    async def is_revoked(self, jti: str) -> bool:
        """Always returns False — no revocation store is consulted."""
        return False

    async def revoke(self, jti: str, expires_at: datetime) -> None:
        """No-op — revocation records are not persisted."""
