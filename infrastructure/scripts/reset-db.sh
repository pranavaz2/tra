#!/usr/bin/env sh
# =============================================================================
# reset-db.sh
#
# Drops and recreates the local development database, then runs all Alembic
# migrations from scratch. Intended for local development only.
#
# SAFETY GATES (all must pass before any destructive action):
#   1. APP_ENV must be "local" — refuses to run against staging or production
#   2. DATABASE_URL must be set
#   3. Explicit confirmation required — user must type "yes" to proceed
#
# Usage:
#   ./infrastructure/scripts/reset-db.sh
#
# Or via make:
#   make db-reset
#
# What this script does:
#   1. Validates environment (APP_ENV=local, DATABASE_URL present)
#   2. Prompts for confirmation
#   3. Drops the existing database
#   4. Creates a fresh database with the PostGIS extension
#   5. Runs `alembic upgrade head` to apply all migrations
#
# What this script does NOT do:
#   - Touch any database where APP_ENV != local
#   - Run without explicit "yes" confirmation
#   - Run in CI (APP_ENV=ci is also blocked)
# =============================================================================

set -e

# ---------------------------------------------------------------------------
# Safety gate 1: APP_ENV must be "local"
# ---------------------------------------------------------------------------
APP_ENV="${APP_ENV:-}"

if [ -z "$APP_ENV" ]; then
  echo ""
  echo "[reset-db] ERROR: APP_ENV is not set." >&2
  echo "[reset-db] This script requires APP_ENV=local to prevent accidental" >&2
  echo "[reset-db] execution against staging or production databases." >&2
  echo ""
  exit 1
fi

if [ "$APP_ENV" != "local" ]; then
  echo ""
  echo "[reset-db] ERROR: APP_ENV is '${APP_ENV}'." >&2
  echo "[reset-db] This script only runs when APP_ENV=local." >&2
  echo "[reset-db] Refusing to reset a non-local database." >&2
  echo ""
  exit 1
fi

# ---------------------------------------------------------------------------
# Safety gate 2: DATABASE_URL must be set
# ---------------------------------------------------------------------------
DATABASE_SYNC_URL="${DATABASE_SYNC_URL:-}"
DATABASE_URL="${DATABASE_URL:-}"

if [ -z "$DATABASE_SYNC_URL" ] && [ -z "$DATABASE_URL" ]; then
  echo ""
  echo "[reset-db] ERROR: Neither DATABASE_SYNC_URL nor DATABASE_URL is set." >&2
  echo "[reset-db] Set DATABASE_SYNC_URL in your .env file." >&2
  echo ""
  exit 1
fi

# Prefer sync URL for psql/dropdb/createdb operations
if [ -n "$DATABASE_SYNC_URL" ]; then
  CLEAN_URL=$(echo "$DATABASE_SYNC_URL" | sed 's|postgresql+[a-zA-Z0-9_]*://|postgresql://|')
else
  CLEAN_URL=$(echo "$DATABASE_URL" | sed 's|postgresql+[a-zA-Z0-9_]*://|postgresql://|')
fi

DB_HOST=$(echo "$CLEAN_URL" | sed -n 's|.*://[^:@]*:*[^@]*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$CLEAN_URL" | sed -n 's|.*://[^:@]*:*[^@]*@[^:/]*:\([0-9]*\)/.*|\1|p')
DB_USER=$(echo "$CLEAN_URL" | sed -n 's|.*://\([^:@]*\).*@.*|\1|p')
DB_NAME=$(echo "$CLEAN_URL" | sed -n 's|.*/\([^?]*\).*|\1|p')
DB_PORT="${DB_PORT:-5432}"

echo ""
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│                    DATABASE RESET WARNING                       │"
echo "├─────────────────────────────────────────────────────────────────┤"
echo "│  This will PERMANENTLY DELETE all data in the database below.  │"
echo "│  All tables, rows, and schema objects will be destroyed.        │"
echo "│                                                                 │"
printf "│  Host:     %-52s│\n" "${DB_HOST}:${DB_PORT}"
printf "│  Database: %-52s│\n" "${DB_NAME}"
printf "│  User:     %-52s│\n" "${DB_USER}"
echo "│                                                                 │"
echo "│  APP_ENV is 'local' — proceeding is allowed.                   │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""

# ---------------------------------------------------------------------------
# Safety gate 3: Explicit confirmation
# ---------------------------------------------------------------------------
printf "Type 'yes' to confirm the reset, or anything else to abort: "
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
  echo ""
  echo "[reset-db] Aborted. Database was not modified."
  exit 0
fi

echo ""
echo "[reset-db] Confirmation received. Starting database reset..."

# ---------------------------------------------------------------------------
# Drop and recreate the database
# ---------------------------------------------------------------------------
export PGPASSWORD
PGPASSWORD=$(echo "$CLEAN_URL" | sed -n 's|.*://[^:]*:\([^@]*\)@.*|\1|p')

echo "[reset-db] Dropping database '${DB_NAME}'..."
dropdb \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --username="${DB_USER}" \
  --if-exists \
  "${DB_NAME}"

echo "[reset-db] Creating database '${DB_NAME}'..."
createdb \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --username="${DB_USER}" \
  "${DB_NAME}"

echo "[reset-db] Enabling PostGIS extension..."
psql \
  --host="${DB_HOST}" \
  --port="${DB_PORT}" \
  --username="${DB_USER}" \
  --dbname="${DB_NAME}" \
  --command="CREATE EXTENSION IF NOT EXISTS postgis;"

echo "[reset-db] Running Alembic migrations..."
cd "$(dirname "$0")/../../apps/api"
alembic upgrade head

echo ""
echo "[reset-db] Done. Database '${DB_NAME}' has been reset and is up to date."
