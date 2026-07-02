#!/usr/bin/env sh
# =============================================================================
# check-env.sh
#
# Validates that all required environment variables are set before starting a
# service or running migrations. Exits 1 with a clear error listing missing
# variables. Exits 0 if all required variables are present.
#
# Usage:
#   ./check-env.sh                   # Checks all required variables
#   ./check-env.sh --api-only        # Checks only API service variables
#   ./check-env.sh --db-only         # Checks only database variables
#
# This script reads variable NAMES — never values. No secrets are printed.
# =============================================================================

set -e

MODE="${1:-all}"

# ---------------------------------------------------------------------------
# Variable groups
# ---------------------------------------------------------------------------
DB_REQUIRED="
DATABASE_URL
DATABASE_SYNC_URL
"

REDIS_REQUIRED="
REDIS_URL
"

SECURITY_REQUIRED="
SECRET_KEY
JWT_SECRET_KEY
"

APP_REQUIRED="
APP_ENV
"

PROVIDERS_REQUIRED="
AI_PROVIDER
MAPS_PROVIDER
EMAIL_PROVIDER
STORAGE_PROVIDER
NOTIFICATION_PROVIDER
"

# Variables required ONLY in production (APP_ENV=production)
PRODUCTION_REQUIRED="
CORS_ALLOWED_ORIGINS
APP_VERSION
"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
MISSING=""

check_var() {
  VAR_NAME="$1"
  # Strip leading/trailing whitespace and skip empty lines
  VAR_NAME=$(echo "$VAR_NAME" | tr -d '[:space:]')
  [ -z "$VAR_NAME" ] && return

  eval VAL=\$"${VAR_NAME}"
  if [ -z "$VAL" ]; then
    MISSING="${MISSING}  - ${VAR_NAME}\n"
  fi
}

check_group() {
  VARS="$1"
  for VAR in $VARS; do
    check_var "$VAR"
  done
}

# ---------------------------------------------------------------------------
# Run checks based on mode
# ---------------------------------------------------------------------------
echo "[check-env] Checking environment variables (mode: ${MODE})..."

case "$MODE" in
  --db-only)
    check_group "$DB_REQUIRED"
    ;;
  --api-only)
    check_group "$APP_REQUIRED"
    check_group "$DB_REQUIRED"
    check_group "$REDIS_REQUIRED"
    check_group "$SECURITY_REQUIRED"
    check_group "$PROVIDERS_REQUIRED"
    ;;
  all|*)
    check_group "$APP_REQUIRED"
    check_group "$DB_REQUIRED"
    check_group "$REDIS_REQUIRED"
    check_group "$SECURITY_REQUIRED"
    check_group "$PROVIDERS_REQUIRED"

    # Additional checks for production
    if [ "${APP_ENV:-}" = "production" ]; then
      echo "[check-env] Production environment detected — checking production-only variables..."
      check_group "$PRODUCTION_REQUIRED"
    fi
    ;;
esac

# ---------------------------------------------------------------------------
# Report results
# ---------------------------------------------------------------------------
if [ -n "$MISSING" ]; then
  echo ""
  echo "[check-env] ERROR: The following required environment variables are not set:"
  printf "%b" "$MISSING"
  echo ""
  echo "[check-env] Copy .env.example to .env and fill in the required values."
  echo ""
  exit 1
fi

echo "[check-env] All required environment variables are set."
