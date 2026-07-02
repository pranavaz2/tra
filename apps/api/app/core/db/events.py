"""
Travix AI — SQLAlchemy Engine Event Hooks

Attaches query timing and slow query detection to an async engine without
requiring any external monitoring SDK.

Why sync-level events on an async engine?
  SQLAlchemy's async engine wraps a synchronous engine at the DBAPI level.
  All cursor execution events (before_cursor_execute, after_cursor_execute)
  fire on the underlying sync engine — they are DBAPI-level events, not
  async-level events. Access the sync engine via `engine.sync_engine`.

Hooks registered:
  - before_cursor_execute  → stores query start time on the connection context
  - after_cursor_execute   → computes elapsed time, logs at DEBUG or WARNING

Slow query threshold:
  Configured via `DB_SLOW_QUERY_THRESHOLD_MS` (default 200 ms).
  Queries above the threshold are logged at WARNING level with the statement
  preview. Queries below are logged at DEBUG level (suppressed in production).

Usage — called once at engine creation time:

    from app.core.db.events import register_query_hooks
    engine = create_async_engine(url, ...)
    register_query_hooks(engine, threshold_ms=200.0)
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

_DEFAULT_THRESHOLD_MS: float = 200.0
_STATEMENT_PREVIEW_LENGTH: int = 500


def register_query_hooks(
    engine: AsyncEngine,
    *,
    threshold_ms: float = _DEFAULT_THRESHOLD_MS,
) -> None:
    """
    Register query timing and slow query detection on the engine's sync core.

    Must be called once immediately after the engine is created. Re-registering
    on the same engine will duplicate the listeners — guard with ``if not already
    registered`` if needed, or call only from ``_build_engine()``.

    Args:
        engine:       The async engine returned by ``create_async_engine()``.
        threshold_ms: Queries exceeding this duration (in milliseconds) are
                      logged at WARNING level. Defaults to 200 ms.
    """

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _before(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,  # noqa: FBT001
    ) -> None:
        context._query_start_time = time.monotonic()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def _after(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,  # noqa: FBT001
    ) -> None:
        elapsed_ms = (time.monotonic() - context._query_start_time) * 1000

        preview = statement[:_STATEMENT_PREVIEW_LENGTH].replace("\n", " ")

        if elapsed_ms >= threshold_ms:
            logger.warning(
                "Slow query detected",
                extra={
                    "elapsed_ms": round(elapsed_ms, 2),
                    "threshold_ms": threshold_ms,
                    "statement_preview": preview,
                },
            )
        else:
            logger.debug(
                "Query executed",
                extra={
                    "elapsed_ms": round(elapsed_ms, 2),
                    "statement_preview": preview[:200],
                },
            )

    logger.debug("Database query timing hooks registered", extra={"threshold_ms": threshold_ms})
