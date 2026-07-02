# =============================================================================
# Travix AI — API Dockerfile (Production)
#
# Multi-stage build:
#   Stage 1 (builder)  Install runtime dependencies into /opt/venv
#   Stage 2 (runtime)  Minimal image — venv + source only, no build tools
#
# Resulting image contains:
#   - Python 3.12 slim runtime
#   - Runtime pip packages only (no dev/test dependencies)
#   - Application source in /app/app/
#   - Non-root travix user (UID 1001)
#   - Health check on GET /health
#
# Build:
#   docker build -t travix-api:latest .
#
# Run (requires environment variables or --env-file):
#   docker run -p 8000:8000 --env-file .env travix-api:latest
# =============================================================================


# =============================================================================
# Stage 1: builder
# Installs Python dependencies into an isolated virtual environment.
# This stage is discarded in the final image — only /opt/venv is copied.
# =============================================================================
FROM python:3.14-slim AS builder

# Install build-time system dependencies (C compiler, libpq headers)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only.
# Copy pyproject.toml first — this layer is cached until deps change.
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "."


# =============================================================================
# Stage 2: runtime
# Minimal image — no build tools, no compilers, no dev packages.
# Runs as non-root user travix (UID 1001).
# =============================================================================
FROM python:3.14-slim AS runtime

# Create non-root user before any other setup
RUN groupadd --system --gid 1001 travix \
    && useradd --system --uid 1001 --gid travix --no-create-home travix

# Install only runtime system libraries (no headers, no compiler)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy only the application source (not pyproject.toml, tests, migrations CLI)
# Migrations are run via `alembic upgrade head` before the API starts — not baked in
COPY --chown=travix:travix app/ ./app/

# Switch to non-root user for all subsequent instructions and at runtime
USER travix

EXPOSE 8000

# Liveness check — polls GET /health which never touches the database
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health || exit 1

# Use gunicorn with a single uvicorn worker class.
# Worker count is 1 here — scale horizontally via container replicas,
# not by increasing workers (async code is not CPU-bound).
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "1", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
