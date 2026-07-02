#!/usr/bin/env sh
# =============================================================================
# generate-secret.sh
#
# Generates a cryptographically secure random secret suitable for use as
# SECRET_KEY or JWT_SECRET_KEY in the application configuration.
#
# Output: A 64-byte (512-bit) hex-encoded secret printed to stdout.
#
# Usage:
#   ./generate-secret.sh
#   ./generate-secret.sh 32        # 32-byte (256-bit) secret
#   ./generate-secret.sh 64 base64 # 64-byte secret in base64 encoding
#
# Add to .env:
#   SECRET_KEY=$(./infrastructure/scripts/generate-secret.sh)
#   JWT_SECRET_KEY=$(./infrastructure/scripts/generate-secret.sh)
#
# Or via make:
#   make generate-secrets
# =============================================================================

set -e

BYTES="${1:-64}"
ENCODING="${2:-hex}"

# ---------------------------------------------------------------------------
# Validate byte count
# ---------------------------------------------------------------------------
case "$BYTES" in
  [0-9]|[0-9][0-9]|[0-9][0-9][0-9])
    if [ "$BYTES" -lt 16 ]; then
      echo "[generate-secret] ERROR: Minimum secret length is 16 bytes (128 bits)." >&2
      exit 1
    fi
    ;;
  *)
    echo "[generate-secret] ERROR: Invalid byte count '${BYTES}'. Must be a positive integer." >&2
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# Generate using the best available source
# ---------------------------------------------------------------------------
if command -v openssl > /dev/null 2>&1; then
  case "$ENCODING" in
    base64)
      openssl rand -base64 "$BYTES"
      ;;
    hex|*)
      openssl rand -hex "$BYTES"
      ;;
  esac
elif [ -r /dev/urandom ]; then
  case "$ENCODING" in
    base64)
      dd if=/dev/urandom bs="$BYTES" count=1 2>/dev/null | base64
      ;;
    hex|*)
      dd if=/dev/urandom bs="$BYTES" count=1 2>/dev/null | xxd -p | tr -d '\n'
      echo
      ;;
  esac
else
  echo "[generate-secret] ERROR: No cryptographic random source available." >&2
  echo "[generate-secret] Install openssl or ensure /dev/urandom is accessible." >&2
  exit 1
fi
