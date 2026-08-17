"""
Travix AI — FastAPI Application Factory

Entry point for the ASGI application.

The app is created by create_app() which:
  1. Configures structured logging
  2. Initialises monitoring (Sentry, if configured)
  3. Registers the lifespan context (startup/shutdown)
  4. Applies middleware in the correct order
  5. Registers global exception handlers
  6. Mounts routers

The module-level `app` object is what uvicorn/gunicorn imports:
    uvicorn app.main:app

Adding a new feature module:
  1. Create apps/api/app/modules/{module_name}/ per CLAUDE.md Section 5.
  2. Import the module's router.
  3. Call api_v1_router.include_router(router) below (in the marked section).
  4. Never add business logic to this file.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import unhandled_exception_handler, validation_exception_handler
from app.core.health import router as health_router
from app.core.middleware.request_id import RequestIDMiddleware
from app.core.middleware.security_headers import SecurityHeadersMiddleware
from app.core.middleware.timing import TimingMiddleware
from app.core.monitoring import configure_monitoring
from app.core.security.auth.errors import AuthorizationError
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


async def _authorization_error_handler(
    request: Request,  # noqa: ARG001  (required by FastAPI exception handler signature)
    exc: AuthorizationError,
) -> "JSONResponse":
    """Convert AuthorizationError to an RFC 7807 JSONResponse."""
    from fastapi.responses import JSONResponse

    return exc.to_response()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Startup: log the boot event. Resources (DB engine, Redis clients) are
    initialised lazily on first use rather than eagerly here, so startup
    is fast and CI tests do not require live dependencies.

    Shutdown: dispose the DB connection pool and close all Redis connections.
    """
    s = get_settings()
    logger.info(
        "Travix AI API starting",
        extra={"version": s.app_version, "environment": s.app_env},
    )

    yield

    from app.database import close_db
    from app.redis import close_redis

    await close_db()
    await close_redis()
    logger.info("Travix AI API stopped")


def create_app() -> FastAPI:
    """
    Construct and return the configured FastAPI application.

    Called once at module load time. The result is bound to the module-level
    `app` variable which the ASGI server imports.
    """
    configure_logging()

    s = get_settings()

    configure_monitoring(s)

    app = FastAPI(
        title="Travix AI API",
        description="AI-powered travel planning platform",
        version=s.app_version,
        docs_url="/docs" if s.show_docs else None,
        redoc_url="/redoc" if s.show_docs else None,
        openapi_url="/openapi.json" if s.show_docs else None,
        lifespan=_lifespan,
    )

    # ----------------------------------------------------------------- #
    # Exception handlers                                                  #
    # ----------------------------------------------------------------- #
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AuthorizationError, _authorization_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ----------------------------------------------------------------- #
    # Middleware                                                           #
    #                                                                     #
    # FastAPI/Starlette applies middleware in reverse registration order: #
    # the LAST add_middleware() call executes FIRST on inbound requests.  #
    # ----------------------------------------------------------------- #

    # 1st to execute on requests (outermost): CORS preflight handling
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=s.cors_allowed_methods,
        allow_headers=s.cors_allowed_headers,
    )

    # 2nd: inject security headers on every response
    app.add_middleware(SecurityHeadersMiddleware, production=s.is_production)

    # 3rd: measure wall-clock request time, add X-Response-Time header
    app.add_middleware(TimingMiddleware)

    # 4th (innermost add, outermost execution): assign request/correlation IDs
    # Must execute first so IDs are in context before any logging occurs.
    app.add_middleware(RequestIDMiddleware)

    # ----------------------------------------------------------------- #
    # Routers                                                             #
    # ----------------------------------------------------------------- #

    # Infrastructure endpoints — not versioned, no auth required
    app.include_router(health_router)

    # API v1 router — all feature module routes live under /api/v1/
    # Register feature module routers here as they are implemented:
    #
    #   from app.modules.trips.router import router as trips_router
    #   api_v1_router.include_router(trips_router)
    #
    from app.modules.identity.authentication.presentation.router import (
        router as auth_router,
    )
    from app.modules.locations.router import router as locations_router
    from app.modules.travel.trips.presentation.router import router as trips_router
    from app.modules.travel.itinerary.presentation.router import router as itinerary_router
    from app.modules.travel.planning.presentation.router import router as planning_router
    from app.modules.travel.budget.presentation.router import router as budget_router
    from app.modules.travel.sharing.presentation.router import (
        router as sharing_router,
        public_router as sharing_public_router,
    )
    from app.modules.travel.media.presentation.router import router as media_router
    from app.modules.travel.recommendations.presentation.router import (
        router as recommendations_router,
    )

    api_v1_router = APIRouter(prefix="/api/v1")
    api_v1_router.include_router(auth_router)
    api_v1_router.include_router(locations_router)
    api_v1_router.include_router(trips_router)
    api_v1_router.include_router(itinerary_router)
    api_v1_router.include_router(planning_router)
    api_v1_router.include_router(budget_router)
    api_v1_router.include_router(sharing_router)
    api_v1_router.include_router(sharing_public_router)
    api_v1_router.include_router(media_router)
    api_v1_router.include_router(recommendations_router)
    app.include_router(api_v1_router)

    logger.info("Application routes registered")
    return app


# ASGI application object — imported by uvicorn and gunicorn
app = create_app()
