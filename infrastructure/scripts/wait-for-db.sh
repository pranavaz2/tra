#!/usr/bin/env sh
# =============================================================================
# wait-for-db.sh
#
# Polls PostgreSQL until it accepts connections, then exits 0.
# Exits 1 if the database is not ready within the timeout.
#
# Usage:
#   ./wait-for-db.sh [timeout_seconds]
#
# Environment variables required:
#   DATABASE_URL or individual POSTGRES_* variables
#
# Examples:
#   ./wait-for-db.sh          # 60 second timeout (default)
#   ./wait-for-db.sh 120      # 120 second timeout
#
# Typically used as an entrypoint prefix in docker-compose:
#   command: sh -c "./infrastructure/scripts/wait-for-db.sh && alembic upgrade head && uvicorn ..."
# =============================================================================

set -e

TIMEOUT="${1:-60}"
ELAPSED=0
SLEEP_INTERVAL=2

# ---------------------------------------------------------------------------
# Resolve connection parameters from DATABASE_URL or POSTGRES_* env vars
# ---------------------------------------------------------------------------
if [ -n "${DATABASE_URL:-}" ]; then
  # Strip the driver prefix (postgresql+asyncpg:// → postgresql://)
  CLEAN_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+[a-zA-Z0-9_]*://|postgresql://|')
  DB_HOST=$(echo "$CLEAN_URL" | sed -n 's|.*://[^:@]*:*[^@]*@\([^:/]*\).*|\1|p')
  DB_PORT=$(echo "$CLEAN_URL" | sed -n 's|.*://[^:@]*:*[^@]*@[^:/]*:\([0-9]*\)/.*|\1|p')
  DB_USER=$(echo "$CLEAN_URL" | sed -n 's|.*://\([^:@]*\).*@.*|\1|p')
  DB_NAME=$(echo "$CLEAN_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')
else
  DB_HOST="${POSTGRES_HOST:-localhost}"
  DB_PORT="${POSTGRES_PORT:-5432}"
  DB_USER="${POSTGRES_USER:-travix}"
  DB_NAME="${POSTGRES_DB:-travix}"
fi

DB_PORT="${DB_PORT:-5432}"

echo "[wait-for-db] Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT} (timeout: ${TIMEOUT}s)..."

# ---------------------------------------------------------------------------
# Polling loop — uses pg_isready which does not require a password
# ---------------------------------------------------------------------------
until pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -q; do
  ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
  if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "[wait-for-db] ERROR: PostgreSQL not ready after ${TIMEOUT}s. Giving up." >&2
    exit 1
  fi
  echo "[wait-for-db] Not ready yet (${ELAPSED}s elapsed). Retrying in ${SLEEP_INTERVAL}s..."
  sleep "${SLEEP_INTERVAL}"
done

echo "[wait-for-db] PostgreSQL is ready at ${DB_HOST}:${DB_PORT}."
