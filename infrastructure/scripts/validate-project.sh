#!/usr/bin/env sh
# =============================================================================
# validate-project.sh
#
# Validates the Travix AI repository structure and enforces architectural rules
# that cannot be caught by a standard linter. Run this in CI and pre-push hooks
# to catch structural regressions early.
#
# Checks performed:
#   1. Required files exist at expected paths
#   2. Required directories exist
#   3. No direct os.environ usage in app code (must use Pydantic settings)
#   4. No direct provider SDK imports in feature modules
#      (must go through app/services/ abstraction layer)
#   5. No print() calls in Python application code
#   6. apps/api/__init__.py exists in all Python packages
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed (issues are printed before exit)
#
# Usage:
#   ./infrastructure/scripts/validate-project.sh
#   make validate          (if wired into Makefile)
# =============================================================================

set -e

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0
ISSUES=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pass() {
  PASS=$((PASS + 1))
}

fail() {
  FAIL=$((FAIL + 1))
  ISSUES="${ISSUES}  ✗ ${1}\n"
}

check_file() {
  if [ -f "$1" ]; then
    pass
  else
    fail "Required file missing: $1"
  fi
}

check_dir() {
  if [ -d "$1" ]; then
    pass
  else
    fail "Required directory missing: $1"
  fi
}

# ---------------------------------------------------------------------------
# Check 1: Required files
# ---------------------------------------------------------------------------
echo "[validate-project] Checking required files..."

check_file "CLAUDE.md"
check_file "README.md"
check_file "CONTRIBUTING.md"
check_file "CHANGELOG.md"
check_file "LICENSE"
check_file "SECURITY.md"
check_file "CODE_OF_CONDUCT.md"
check_file "VERSION"
check_file ".env.example"
check_file ".editorconfig"
check_file ".gitignore"
check_file ".gitattributes"
check_file ".pre-commit-config.yaml"
check_file "Makefile"
check_file ".github/dependabot.yml"
check_file ".github/PULL_REQUEST_TEMPLATE.md"
check_file ".github/CODEOWNERS"
check_file ".github/workflows/ci.yml"
check_file "apps/api/pyproject.toml"
check_file "apps/api/.python-version"
check_file "apps/api/alembic.ini"
check_file "apps/api/Dockerfile"
check_file "apps/api/Dockerfile.dev"
check_file "apps/api/app/main.py"
check_file "apps/api/app/config.py"
check_file "apps/api/app/database.py"
check_file "apps/api/app/redis.py"
check_file "apps/api/app/dependencies.py"
check_file "apps/api/app/logging_config.py"
check_file "apps/api/app/core/health.py"
check_file "apps/api/app/core/exceptions.py"
check_file "apps/api/app/core/pagination.py"
check_file "apps/api/app/core/monitoring.py"
check_file "apps/api/app/core/middleware/request_id.py"
check_file "apps/api/app/core/middleware/timing.py"
check_file "apps/api/app/core/middleware/security_headers.py"
check_file "infrastructure/compose/docker-compose.yml"
check_file "infrastructure/compose/docker-compose.override.yml"
check_file "infrastructure/compose/docker-compose.prod.yml"

# ---------------------------------------------------------------------------
# Check 2: Required directories
# ---------------------------------------------------------------------------
echo "[validate-project] Checking required directories..."

check_dir "apps/api"
check_dir "apps/mobile"
check_dir "apps/api/app"
check_dir "apps/api/app/core"
check_dir "apps/api/app/core/middleware"
check_dir "apps/api/app/core/security"
check_dir "apps/api/app/modules"
check_dir "apps/api/migrations"
check_dir "apps/api/tests"
check_dir "docs/adr"
check_dir "docs/tasks"
check_dir "infrastructure/compose"
check_dir "infrastructure/scripts"
check_dir "infrastructure/docker"

# ---------------------------------------------------------------------------
# Check 3: No os.environ direct access in application code
# ---------------------------------------------------------------------------
echo "[validate-project] Checking for os.environ usage in app code..."

if [ -d "apps/api/app" ]; then
  MATCHES=$(grep -r --include="*.py" "os\.environ" apps/api/app/ 2>/dev/null | \
            grep -v "# " | wc -l | tr -d ' ')
  if [ "$MATCHES" -gt 0 ]; then
    fail "Found $MATCHES os.environ usage(s) in apps/api/app/ — use get_settings() instead"
    grep -r --include="*.py" -n "os\.environ" apps/api/app/ 2>/dev/null | grep -v "# " | \
      while read -r line; do
        ISSUES="${ISSUES}    → ${line}\n"
      done
  else
    pass
  fi
fi

# ---------------------------------------------------------------------------
# Check 4: No direct provider SDK imports in feature modules
# ---------------------------------------------------------------------------
echo "[validate-project] Checking for provider SDK imports in modules/..."

if [ -d "apps/api/app/modules" ]; then
  BANNED_IMPORTS="openai anthropic boto3 google.cloud googlemaps twilio stripe sendgrid firebase_admin"
  MODULE_VIOLATIONS=0
  for sdk in $BANNED_IMPORTS; do
    MATCHES=$(grep -r --include="*.py" "import ${sdk}" apps/api/app/modules/ 2>/dev/null | wc -l | tr -d ' ')
    if [ "$MATCHES" -gt 0 ]; then
      MODULE_VIOLATIONS=$((MODULE_VIOLATIONS + MATCHES))
      fail "Direct import of '${sdk}' in feature modules — use app/services/ abstraction instead"
    fi
  done
  if [ "$MODULE_VIOLATIONS" -eq 0 ]; then
    pass
  fi
fi

# ---------------------------------------------------------------------------
# Check 5: No print() in Python application code
# ---------------------------------------------------------------------------
echo "[validate-project] Checking for print() calls in app code..."

if [ -d "apps/api/app" ]; then
  PRINT_MATCHES=$(grep -r --include="*.py" -n "^\s*print(" apps/api/app/ 2>/dev/null | \
                  grep -v "# " | wc -l | tr -d ' ')
  if [ "$PRINT_MATCHES" -gt 0 ]; then
    fail "Found $PRINT_MATCHES print() call(s) in apps/api/app/ — use logging instead"
  else
    pass
  fi
fi

# ---------------------------------------------------------------------------
# Check 6: __init__.py exists in all Python packages under app/
# ---------------------------------------------------------------------------
echo "[validate-project] Checking Python package __init__.py files..."

if [ -d "apps/api/app" ]; then
  find apps/api/app -type d | while read -r dir; do
    # Skip __pycache__ and hidden dirs
    case "$dir" in
      */__pycache__*|*/.*)
        continue
        ;;
    esac
    if [ ! -f "${dir}/__init__.py" ]; then
      FAIL=$((FAIL + 1))
      ISSUES="${ISSUES}  ✗ Missing __init__.py in Python package: ${dir}\n"
    fi
  done
  pass
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
echo ""
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│                   Project Validation Report                     │"
echo "├─────────────────────────────────────────────────────────────────┤"
printf "│  Passed: %-56s│\n" "${PASS}"
printf "│  Failed: %-56s│\n" "${FAIL}"
echo "└─────────────────────────────────────────────────────────────────┘"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo "Issues found:"
  printf "%b" "$ISSUES"
  echo ""
  echo "[validate-project] FAILED. Fix the issues above before proceeding."
  exit 1
fi

echo ""
echo "[validate-project] All checks passed."
