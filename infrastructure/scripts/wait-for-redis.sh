#!/usr/bin/env sh
# =============================================================================
# wait-for-redis.sh
#
# Polls Redis until it responds to PING, then exits 0.
# Exits 1 if Redis is not ready within the timeout.
#
# Usage:
#   ./wait-for-redis.sh [timeout_seconds]
#
# Environment variables:
#   REDIS_URL   Full Redis URL (redis://[:password@]host[:port][/db])
#               Falls back to REDIS_HOST / REDIS_PORT if not set.
#
# Examples:
#   ./wait-for-redis.sh          # 60 second timeout (default)
#   ./wait-for-redis.sh 30       # 30 second timeout
# =============================================================================

set -e

TIMEOUT="${1:-60}"
ELAPSED=0
SLEEP_INTERVAL=2

# ---------------------------------------------------------------------------
# Resolve connection parameters
# ---------------------------------------------------------------------------
if [ -n "${REDIS_URL:-}" ]; then
  # Extract host and port from redis://[:password@]host[:port][/db]
  REDIS_HOST=$(echo "$REDIS_URL" | sed -n 's|redis://\([^:@/]*\).*|\1|p; s|redis://[^@]*@\([^:/]*\).*|\1|p' | tail -1)
  REDIS_PORT=$(echo "$REDIS_URL" | sed -n 's|.*:\([0-9][0-9]*\)/.*|\1|p; s|.*:\([0-9][0-9]*\)$|\1|p' | tail -1)
  REDIS_HOST="${REDIS_HOST:-localhost}"
  REDIS_PORT="${REDIS_PORT:-6379}"
else
  REDIS_HOST="${REDIS_HOST:-localhost}"
  REDIS_PORT="${REDIS_PORT:-6379}"
fi

echo "[wait-for-redis] Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT} (timeout: ${TIMEOUT}s)..."

# ---------------------------------------------------------------------------
# Polling loop — sends PING and checks for PONG response
# ---------------------------------------------------------------------------
until redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" ping 2>/dev/null | grep -q "PONG"; do
  ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "[wait-for-redis] ERROR: Redis not ready after ${TIMEOUT}s. Giving up." >&2
    exit 1
  fi
  echo "[wait-for-redis] Not ready yet (${ELAPSED}s elapsed). Retrying in ${SLEEP_INTERVAL}s..."
  sleep "${SLEEP_INTERVAL}"
done

echo "[wait-for-redis] Redis is ready at ${REDIS_HOST}:${REDIS_PORT}."
