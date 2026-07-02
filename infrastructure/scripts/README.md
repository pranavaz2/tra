# infrastructure/scripts/ — Developer and CI Utility Scripts

This folder contains **shell scripts** for common developer and CI/CD operations that are
too complex for a single Makefile line but don't belong in application code.

---

## Purpose

Scripts in this folder automate repetitive infrastructure and development tasks:
database seeding, environment validation, secret rotation helpers, CI utilities, and
deployment helpers. They are the "plumbing" that keeps the development workflow smooth.

---

## Scripts

| Script | Purpose | Status |
|---|---|---|
| [`check-env.sh`](check-env.sh) | Validate required environment variables before service startup | Available |
| [`wait-for-db.sh`](wait-for-db.sh) | Poll PostgreSQL until it accepts connections | Available |
| [`wait-for-redis.sh`](wait-for-redis.sh) | Poll Redis until it responds to PING | Available |
| [`generate-secret.sh`](generate-secret.sh) | Generate cryptographically secure random secrets | Available |
| [`reset-db.sh`](reset-db.sh) | Drop and recreate the local development database (local only) | Available |
| [`validate-project.sh`](validate-project.sh) | Validate repository structure and architectural rules (CI gate) | Available |
| `seed-db.sh` | Seed the database with development data | Planned |

---

## Script Standards

All scripts in this folder must follow these standards:

- **Shebang:** `#!/usr/bin/env sh` — POSIX sh for maximum portability across CI environments
- **Strict mode:** Begin every script with `set -e`
- **Idempotent:** Running a script multiple times must produce the same result
- **No secrets in scripts:** Scripts read secrets from environment variables only
- **Logging:** Use echo with prefixes: `[script-name] message`
- **Exit codes:** Exit 0 on success, non-zero on failure with a clear error message printed to stderr

---

## Example Structure

```bash
#!/usr/bin/env bash
set -euo pipefail

# Script name and purpose
# Usage: ./scripts/check_env.sh

REQUIRED_VARS=(
    "DATABASE_URL"
    "REDIS_URL"
    "JWT_SECRET_KEY"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo "[ERROR] Required environment variable '$var' is not set."
        exit 1
    fi
done

echo "[INFO] All required environment variables are set."
```

