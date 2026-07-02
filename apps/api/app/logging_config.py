"""
Travix AI — Structured Logging Configuration

Configures Python's standard logging module with either:
  - JSON output (non-local environments) for log aggregation tools
  - Human-readable text output (local development)

Call configure_logging() once at application startup (in app.main.create_app).

Log record fields emitted in JSON mode:
  timestamp     ISO 8601 UTC with millisecond precision
  level         DEBUG | INFO | WARNING | ERROR | CRITICAL
  logger        Dot-separated module path (e.g. "travix.modules.trips.service")
  message       Human-readable event description
  request_id    Injected by RequestIDMiddleware via ContextVar
  environment   APP_ENV value

Application code must use the standard logging module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Trip created", extra={"trip_id": str(trip.id)})

Never use print() in application code.
"""

from __future__ import annotations

import logging
import sys


def configure_logging() -> None:
    """
    Configure root logger based on application settings.

    Must be called before the first log message is emitted — typically at
    the top of create_app() in app.main before any other setup runs.
    """
    from app.config import get_settings

    s = get_settings()
    log_level = getattr(logging, s.log_level, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    if s.log_format == "json":
        handler.setFormatter(_build_json_formatter(s.app_env, s.app_version))
    else:
        handler.setFormatter(_build_text_formatter())

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)

    _tune_library_loggers(s.is_local)

    logging.getLogger(__name__).debug(
        "Logging configured",
        extra={"format": s.log_format, "level": s.log_level},
    )


def _build_json_formatter(environment: str, version: str) -> logging.Formatter:
    """
    Build a JSON log formatter.

    Uses python-json-logger if available; falls back to a plain text
    formatter so the app starts even if the library is missing (though
    this should never happen in a correctly installed environment).
    """
    try:
        from pythonjsonlogger.json import JsonFormatter

        class _TravixJsonFormatter(JsonFormatter):  # type: ignore[misc]
            def add_fields(
                self,
                log_record: dict,  # type: ignore[type-arg]
                record: logging.LogRecord,
                message_dict: dict,  # type: ignore[type-arg]
            ) -> None:
                super().add_fields(log_record, record, message_dict)
                # Inject static context on every line
                log_record["environment"] = environment
                log_record["version"] = version
                # Inject request-scoped context from ContextVars
                try:
                    from app.core.middleware.request_id import (
                        get_correlation_id,
                        get_request_id,
                    )

                    if rid := get_request_id():
                        log_record["request_id"] = rid
                    if cid := get_correlation_id():
                        log_record["correlation_id"] = cid
                except Exception:
                    pass

        return _TravixJsonFormatter(
            fmt="%(timestamp)s %(level)s %(logger)s %(message)s",
            rename_fields={
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger",
            },
            timestamp=True,
        )
    except ImportError:
        logging.warning(
            "python-json-logger not installed; falling back to text logging."
        )
        return _build_text_formatter()


def _build_text_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _tune_library_loggers(is_local: bool) -> None:
    """Suppress noisy library loggers to keep output readable."""
    # uvicorn access logs add nothing beyond our own request logging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    # Show SQLAlchemy SQL statements only in local dev
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if is_local else logging.WARNING
    )
    # Reduce asyncio noise
    logging.getLogger("asyncio").setLevel(logging.WARNING)
