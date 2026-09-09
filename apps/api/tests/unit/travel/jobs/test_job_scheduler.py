"""Unit tests for background job scheduler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock
import pytest

from app.core.jobs.scheduler import AsyncioJobScheduler, JobConfig


@pytest.mark.asyncio
async def test_job_registration_and_immediate_trigger():
    """Verify job registration and manual trigger execution."""
    scheduler = AsyncioJobScheduler()
    executed = False

    async def sample_handler():
        nonlocal executed
        executed = True

    config = JobConfig(job_id="test_job_1", interval_seconds=60.0)
    scheduler.register_job(config, sample_handler)

    status = scheduler.get_job_status("test_job_1")
    assert status is not None
    assert status.runs_count == 0

    triggered = await scheduler.trigger_job("test_job_1")
    assert triggered is True

    # Allow task to run
    await asyncio.sleep(0.05)

    status = scheduler.get_job_status("test_job_1")
    assert status is not None
    assert status.runs_count == 1
    assert status.success_count == 1
    assert status.failure_count == 0
    assert executed is True


@pytest.mark.asyncio
async def test_job_retry_on_failure():
    """Verify scheduler retries on handler failure and captures telemetry."""
    scheduler = AsyncioJobScheduler()
    attempts = 0

    async def failing_handler():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError(f"Transient error on attempt {attempts}")
        # Succeeds on 3rd attempt

    config = JobConfig(
        job_id="retry_job",
        interval_seconds=60.0,
        max_retries=3,
        retry_backoff_seconds=0.01,
    )
    scheduler.register_job(config, failing_handler)

    triggered = await scheduler.trigger_job("retry_job")
    assert triggered is True

    # Allow retry sleep to complete
    await asyncio.sleep(0.1)

    status = scheduler.get_job_status("retry_job")
    assert status is not None
    assert status.success_count == 1
    assert attempts == 3


@pytest.mark.asyncio
async def test_concurrency_lock_prevents_overlapping_runs():
    """Verify job cannot be triggered concurrently while already running."""
    scheduler = AsyncioJobScheduler()

    async def slow_handler():
        await asyncio.sleep(0.2)

    config = JobConfig(job_id="slow_job", interval_seconds=60.0)
    scheduler.register_job(config, slow_handler)

    # First trigger succeeds
    t1 = await scheduler.trigger_job("slow_job")
    assert t1 is True

    # Immediate second trigger is rejected
    t2 = await scheduler.trigger_job("slow_job")
    assert t2 is False

    await asyncio.sleep(0.25)
