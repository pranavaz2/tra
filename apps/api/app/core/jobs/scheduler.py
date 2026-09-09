"""Replaceable background job scheduler infrastructure."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class JobConfig:
    """Configuration for a scheduled background job."""

    job_id: str
    interval_seconds: float
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0
    enabled: bool = True


@dataclass
class JobExecution:
    """Runtime execution telemetry for a scheduled job."""

    job_id: str
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    runs_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: str | None = None
    is_running: bool = False


@runtime_checkable
class IJobScheduler(Protocol):
    """Abstract port for scheduling and executing recurring or one-off background jobs."""

    def register_job(
        self,
        config: JobConfig,
        handler: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a background job handler."""
        ...

    async def trigger_job(self, job_id: str) -> bool:
        """Trigger an immediate execution of a registered job."""
        ...

    def get_job_status(self, job_id: str) -> JobExecution | None:
        """Retrieve execution telemetry for a registered job."""
        ...

    def list_job_statuses(self) -> list[JobExecution]:
        """List statuses for all registered jobs."""
        ...

    async def start(self) -> None:
        """Start background scheduler loop."""
        ...

    async def stop(self) -> None:
        """Gracefully stop scheduler loop."""
        ...


class AsyncioJobScheduler(IJobScheduler):
    """
    Lightweight, development-safe, asyncio-based job scheduler.
    
    Provides concurrency isolation, safe retries, error logging,
    and runtime telemetry without blocking main thread.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, tuple[JobConfig, Callable[[], Coroutine[Any, Any, None]]]] = {}
        self._telemetry: dict[str, JobExecution] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._is_running = False
        self._locks: dict[str, asyncio.Lock] = {}

    def register_job(
        self,
        config: JobConfig,
        handler: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        self._jobs[config.job_id] = (config, handler)
        self._telemetry[config.job_id] = JobExecution(job_id=config.job_id)
        self._locks[config.job_id] = asyncio.Lock()

    def get_job_status(self, job_id: str) -> JobExecution | None:
        return self._telemetry.get(job_id)

    def list_job_statuses(self) -> list[JobExecution]:
        return list(self._telemetry.values())

    async def trigger_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False

        config, handler = self._jobs[job_id]
        lock = self._locks[job_id]
        telemetry = self._telemetry[job_id]

        if lock.locked() or telemetry.is_running:
            logger.info("Job %s is already running, skipping trigger", job_id)
            return False

        telemetry.is_running = True
        asyncio.create_task(self._execute_with_retry(config, handler, telemetry, lock))
        return True

    async def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        logger.info("Starting AsyncioJobScheduler with %d registered jobs", len(self._jobs))

        for job_id, (config, handler) in self._jobs.items():
            if config.enabled:
                self._tasks[job_id] = asyncio.create_task(
                    self._run_job_loop(config, handler, self._telemetry[job_id], self._locks[job_id])
                )

    async def stop(self) -> None:
        self._is_running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        logger.info("Stopped AsyncioJobScheduler")

    async def _run_job_loop(
        self,
        config: JobConfig,
        handler: Callable[[], Coroutine[Any, Any, None]],
        telemetry: JobExecution,
        lock: asyncio.Lock,
    ) -> None:
        while self._is_running:
            try:
                await self._execute_with_retry(config, handler, telemetry, lock)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Unexpected error in job loop for %s: %s", config.job_id, exc)

            try:
                await asyncio.sleep(config.interval_seconds)
            except asyncio.CancelledError:
                break

    async def _execute_with_retry(
        self,
        config: JobConfig,
        handler: Callable[[], Coroutine[Any, Any, None]],
        telemetry: JobExecution,
        lock: asyncio.Lock,
    ) -> None:
        async with lock:
            telemetry.is_running = True
            telemetry.last_run_at = datetime.now(UTC)
            telemetry.runs_count += 1

            try:
                for attempt in range(1, config.max_retries + 1):
                    try:
                        await handler()
                        telemetry.success_count += 1
                        telemetry.last_error = None
                        return
                    except Exception as exc:
                        telemetry.last_error = f"Attempt {attempt}/{config.max_retries} failed: {exc}"
                        logger.warning("Job %s attempt %d failed: %s", config.job_id, attempt, exc)
                        if attempt < config.max_retries:
                            await asyncio.sleep(config.retry_backoff_seconds * attempt)

                telemetry.failure_count += 1
                logger.error("Job %s exhausted all %d retries", config.job_id, config.max_retries)
            finally:
                telemetry.is_running = False
