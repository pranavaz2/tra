# =============================================================================
# Travix AI — Makefile
# Developer task runner for common operations.
# Run `make help` to see all available commands.
# =============================================================================

.DEFAULT_GOAL := help

# Detect the operating system
UNAME_S := $(shell uname -s 2>/dev/null || echo Windows)

# Tool aliases
PYTHON        := python3
PIP           := pip3
FLUTTER       := flutter
DOCKER        := docker
DC            := docker compose
PRE_COMMIT    := pre-commit

# Paths
API_DIR       := apps/api
MOBILE_DIR    := apps/mobile
COMPOSE_DIR   := infrastructure/compose
INFRA_SCRIPTS := infrastructure/scripts

# Docker Compose files
COMPOSE_BASE  := $(COMPOSE_DIR)/docker-compose.yml
COMPOSE_DEV   := $(COMPOSE_DIR)/docker-compose.override.yml
COMPOSE_PROD  := $(COMPOSE_DIR)/docker-compose.prod.yml
COMPOSE_FILE  := $(COMPOSE_BASE)

# Colors for terminal output
BOLD  := \033[1m
RESET := \033[0m
GREEN := \033[32m
YELLOW := \033[33m
CYAN  := \033[36m

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "$(BOLD)Travix AI — Developer Commands$(RESET)"
	@echo ""
	@echo "$(CYAN)Infrastructure$(RESET)"
	@grep -E '^(docker-up|docker-down|docker-restart|docker-logs|docker-ps|docker-build):.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Development$(RESET)"
	@grep -E '^(setup|run-api|run-mobile|run-worker):.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Database$(RESET)"
	@grep -E '^(migrate|migration-new|migration-downgrade|db-reset|db-seed):.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Code Quality$(RESET)"
	@grep -E '^(lint|format|typecheck|pre-commit-run):.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Testing$(RESET)"
	@grep -E '^(test|test-api|test-mobile|test-coverage):.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(CYAN)Utilities$(RESET)"
	@grep -E '^(clean|install-hooks|generate|env-check|generate-secrets|validate):.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*##"}; {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}'
	@echo ""


# =============================================================================
# SETUP
# =============================================================================

.PHONY: setup
setup: ## First-time setup: install all dependencies and hooks
	@echo "$(BOLD)Setting up Travix AI development environment...$(RESET)"
	@$(MAKE) install-hooks
	@$(MAKE) setup-api
	@$(MAKE) setup-mobile
	@echo "$(GREEN)Setup complete. Run 'make docker-up' to start infrastructure.$(RESET)"

.PHONY: setup-api
setup-api: ## Install Python dependencies for the API
	@echo "$(CYAN)Installing API dependencies...$(RESET)"
	cd $(API_DIR) && $(PIP) install -e ".[dev]"

.PHONY: setup-mobile
setup-mobile: ## Install Flutter dependencies for the mobile app
	@echo "$(CYAN)Installing Flutter dependencies...$(RESET)"
	# TODO: Uncomment after apps/mobile/pubspec.yaml is created
	# cd $(MOBILE_DIR) && $(FLUTTER) pub get
	@echo "  [TODO] cd $(MOBILE_DIR) && flutter pub get"

.PHONY: install-hooks
install-hooks: ## Install pre-commit hooks
	@echo "$(CYAN)Installing pre-commit hooks...$(RESET)"
	$(PRE_COMMIT) install
	$(PRE_COMMIT) install --hook-type commit-msg
	@echo "$(GREEN)Pre-commit hooks installed.$(RESET)"


# =============================================================================
# INFRASTRUCTURE — Docker
# =============================================================================

.PHONY: docker-up
docker-up: ## Start all services (PostgreSQL, Redis, API) in development mode
	@echo "$(CYAN)Starting services...$(RESET)"
	$(DC) -f $(COMPOSE_BASE) -f $(COMPOSE_DEV) up -d

.PHONY: docker-down
docker-down: ## Stop and remove all containers (preserves volumes)
	@echo "$(CYAN)Stopping services...$(RESET)"
	$(DC) -f $(COMPOSE_BASE) -f $(COMPOSE_DEV) down

.PHONY: docker-restart
docker-restart: docker-down docker-up ## Restart all services

.PHONY: docker-build
docker-build: ## Rebuild the API development image (run after pyproject.toml changes)
	@echo "$(CYAN)Building API development image...$(RESET)"
	$(DC) -f $(COMPOSE_BASE) -f $(COMPOSE_DEV) build api

.PHONY: docker-logs
docker-logs: ## Tail logs from all running containers
	$(DC) -f $(COMPOSE_BASE) -f $(COMPOSE_DEV) logs -f

.PHONY: docker-ps
docker-ps: ## Show status of all containers
	$(DC) -f $(COMPOSE_BASE) -f $(COMPOSE_DEV) ps


# =============================================================================
# DEVELOPMENT — Running Services
# =============================================================================

.PHONY: run-api
run-api: ## Start the FastAPI development server with hot reload (runs outside Docker)
	@echo "$(CYAN)Starting FastAPI development server...$(RESET)"
	cd $(API_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: run-mobile
run-mobile: ## Start the Flutter app (requires a connected device or emulator)
	@echo "$(CYAN)Starting Flutter development server...$(RESET)"
	# TODO: Uncomment after apps/mobile is initialized
	# cd $(MOBILE_DIR) && $(FLUTTER) run
	@echo "  [TODO] cd $(MOBILE_DIR) && flutter run"

.PHONY: run-worker
run-worker: ## Start the ARQ background task worker
	@echo "$(CYAN)Starting ARQ task worker...$(RESET)"
	# TODO: Uncomment after ARQ is configured
	# cd $(API_DIR) && arq app.worker.WorkerSettings
	@echo "  [TODO] cd $(API_DIR) && arq app.worker.WorkerSettings"


# =============================================================================
# DATABASE — Alembic Migrations
# =============================================================================

.PHONY: migrate
migrate: ## Apply all pending database migrations
	@echo "$(CYAN)Applying database migrations...$(RESET)"
	cd $(API_DIR) && alembic upgrade head

.PHONY: migration-new
migration-new: ## Create a new migration: make migration-new name="add_trips_table"
	@echo "$(CYAN)Creating new migration: $(name)...$(RESET)"
	@if [ -z "$(name)" ]; then echo "$(YELLOW)Usage: make migration-new name=your_migration_name$(RESET)"; exit 1; fi
	cd $(API_DIR) && alembic revision --autogenerate -m "$(name)"

.PHONY: migration-downgrade
migration-downgrade: ## Downgrade database by one migration
	@echo "$(YELLOW)Downgrading database by one migration...$(RESET)"
	cd $(API_DIR) && alembic downgrade -1

.PHONY: db-reset
db-reset: ## Drop and recreate the local database, then re-run migrations (local only)
	@echo "$(YELLOW)Resetting local development database...$(RESET)"
	sh $(INFRA_SCRIPTS)/reset-db.sh

.PHONY: db-seed
db-seed: ## Seed the database with development data
	@echo "$(CYAN)Seeding database...$(RESET)"
	@echo "  [TODO] Implement after seed script is created"


# =============================================================================
# CODE QUALITY — Lint
# =============================================================================

.PHONY: lint
lint: lint-api lint-mobile ## Run all linters (Python + Flutter)

.PHONY: lint-api
lint-api: ## Run Ruff linter on the API
	@echo "$(CYAN)Linting Python (Ruff)...$(RESET)"
	cd $(API_DIR) && ruff check .

.PHONY: lint-mobile
lint-mobile: ## Run dart analyze on the Flutter app
	@echo "$(CYAN)Analyzing Flutter (dart analyze)...$(RESET)"
	# TODO: Uncomment after apps/mobile is initialized
	# cd $(MOBILE_DIR) && $(FLUTTER) analyze
	@echo "  [TODO] cd $(MOBILE_DIR) && flutter analyze"


# =============================================================================
# CODE QUALITY — Format
# =============================================================================

.PHONY: format
format: format-api format-mobile ## Run all formatters (Python + Flutter)

.PHONY: format-api
format-api: ## Format Python code with Black and sort imports with isort
	@echo "$(CYAN)Formatting Python (Black + isort)...$(RESET)"
	cd $(API_DIR) && black . && isort .

.PHONY: format-mobile
format-mobile: ## Format Dart code with dart format
	@echo "$(CYAN)Formatting Dart (dart format)...$(RESET)"
	# TODO: Uncomment after apps/mobile is initialized
	# cd $(MOBILE_DIR) && dart format lib/ test/
	@echo "  [TODO] cd $(MOBILE_DIR) && dart format lib/ test/"

.PHONY: format-check
format-check: ## Check formatting without applying changes (for CI)
	@echo "$(CYAN)Checking formatting...$(RESET)"
	cd $(API_DIR) && black --check . && isort --check-only .


# =============================================================================
# CODE QUALITY — Type Checking
# =============================================================================

.PHONY: typecheck
typecheck: ## Run mypy type checker on the API
	@echo "$(CYAN)Running type checks...$(RESET)"
	cd $(API_DIR) && mypy app/


# =============================================================================
# TESTING
# =============================================================================

.PHONY: test
test: test-api test-mobile ## Run all tests (Python + Flutter)

.PHONY: test-api
test-api: ## Run Python test suite
	@echo "$(CYAN)Running API tests...$(RESET)"
	cd $(API_DIR) && pytest tests/ -v

.PHONY: test-mobile
test-mobile: ## Run Flutter test suite
	@echo "$(CYAN)Running Flutter tests...$(RESET)"
	# TODO: Uncomment after apps/mobile is initialized
	# cd $(MOBILE_DIR) && $(FLUTTER) test
	@echo "  [TODO] cd $(MOBILE_DIR) && flutter test"

.PHONY: test-coverage
test-coverage: ## Run tests and generate coverage report
	@echo "$(CYAN)Running tests with coverage...$(RESET)"
	cd $(API_DIR) && pytest tests/ --cov=app --cov-report=html --cov-report=term-missing


# =============================================================================
# CODE GENERATION
# =============================================================================

.PHONY: generate
generate: generate-mobile ## Run all code generators

.PHONY: generate-mobile
generate-mobile: ## Run build_runner for Riverpod, Drift, and JSON serialization
	@echo "$(CYAN)Running Flutter code generation...$(RESET)"
	# TODO: Uncomment after apps/mobile is initialized
	# cd $(MOBILE_DIR) && dart run build_runner build --delete-conflicting-outputs
	@echo "  [TODO] cd $(MOBILE_DIR) && dart run build_runner build --delete-conflicting-outputs"


# =============================================================================
# PRE-COMMIT
# =============================================================================

.PHONY: pre-commit-run
pre-commit-run: ## Run all pre-commit hooks against all files
	@echo "$(CYAN)Running pre-commit hooks on all files...$(RESET)"
	$(PRE_COMMIT) run --all-files

.PHONY: pre-commit-update
pre-commit-update: ## Update pre-commit hook versions
	$(PRE_COMMIT) autoupdate


# =============================================================================
# UTILITIES
# =============================================================================

.PHONY: clean
clean: ## Remove all build artifacts, caches, and generated files
	@echo "$(YELLOW)Cleaning build artifacts...$(RESET)"
	# Python
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	find . -name ".coverage" -delete 2>/dev/null || true
	# Flutter
	find . -name ".dart_tool" -type d -exec rm -rf {} + 2>/dev/null || true
	# TODO: Add flutter clean after mobile app is initialized
	# cd $(MOBILE_DIR) && $(FLUTTER) clean
	@echo "$(GREEN)Clean complete.$(RESET)"

.PHONY: env-check
env-check: ## Verify required environment variables are set
	@echo "$(CYAN)Checking environment variables...$(RESET)"
	sh $(INFRA_SCRIPTS)/check-env.sh

.PHONY: validate
validate: ## Validate repository structure and architectural rules
	@echo "$(CYAN)Validating project structure...$(RESET)"
	sh $(INFRA_SCRIPTS)/validate-project.sh

.PHONY: generate-secrets
generate-secrets: ## Generate new SECRET_KEY and JWT_SECRET_KEY values
	@echo "$(BOLD)Generated secrets (copy to .env):$(RESET)"
	@echo ""
	@printf "SECRET_KEY="
	@sh $(INFRA_SCRIPTS)/generate-secret.sh
	@printf "JWT_SECRET_KEY="
	@sh $(INFRA_SCRIPTS)/generate-secret.sh
	@echo ""
