"""
Travix AI — Application Monitoring

Initialises external monitoring integrations at application startup.

Currently supported:
  Sentry — error tracking and performance monitoring.
           Enabled when SENTRY_DSN is set in environment variables.

Planned (not yet implemented):
  Prometheus — expose /metrics endpoint for scraping.
  OpenTelemetry — distributed tracing across services.

Usage:
    from app.core.monitoring import configure_monitoring
    configure_monitoring(settings)  # Called once in app.main.create_app()
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def configure_monitoring(settings: object) -> None:
    """
    Initialise all monitoring integrations.

    Called once at startup before any request is handled. Safe to call
    multiple times (subsequent calls are no-ops after first initialisation).

    Args:
        settings: The application Settings instance from app.config.
    """
    _configure_sentry(settings)


def _configure_sentry(settings: object) -> None:
    """
    Initialise Sentry SDK if SENTRY_DSN is configured.

    Sentry captures unhandled exceptions, logs WARNING+, and records
    performance traces for slow requests. The SDK is imported lazily so
    the application starts normally even if sentry-sdk is not installed.

    To enable Sentry:
      1. Add sentry-sdk[fastapi] to pyproject.toml dependencies.
      2. Set SENTRY_DSN in your .env file.

    Sample rate configuration:
      SENTRY_TRACES_SAMPLE_RATE — fraction of requests traced (default 0.1)
      SENTRY_PROFILES_SAMPLE_RATE — fraction of traced requests profiled (default 0.0)
    """
    dsn = getattr(settings, "sentry_dsn", None)
    if not dsn:
        return

    try:
        import sentry_sdk  # type: ignore[import-not-found]
        from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore[import-not-found]
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore[import-not-found]

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=getattr(settings, "sentry_traces_sample_rate", 0.1),
            profiles_sample_rate=getattr(settings, "sentry_profiles_sample_rate", 0.0),
            environment=getattr(settings, "app_env", "unknown"),
            release=getattr(settings, "app_version", "unknown"),
            send_default_pii=False,
        )
        logger.info("Sentry monitoring initialised")
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. "
            "Add sentry-sdk[fastapi] to pyproject.toml to enable error tracking."
        )
