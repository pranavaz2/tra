"""Background Jobs Presentation Layer — FastAPI Router."""

from __future__ import annotations

import logging
from typing import Any, Generic, TypeVar

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from app.core.middleware.request_id import get_request_id
from app.core.security.auth.dependencies import RequireAuthentication
from app.modules.travel.jobs.infrastructure.dependencies import (
    CurrentJobScheduler,
    CurrentTravelIntelligenceJob,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Background Jobs & Travel Intelligence"])

T = TypeVar("T")


class DataEnvelope(BaseModel, Generic[T]):
    """Standard API response envelope."""

    model_config = ConfigDict(frozen=True)
    data: T = Field(description="Payload data")


class JobExecutionResponse(BaseModel):
    """Job status response DTO."""

    model_config = ConfigDict(frozen=True)

    job_id: str
    last_run_at: str | None
    next_run_at: str | None
    runs_count: int
    success_count: int
    failure_count: int
    last_error: str | None
    is_running: bool


@router.post(
    "/travel-intelligence/run",
    status_code=status.HTTP_200_OK,
    summary="Trigger immediate travel intelligence background job check",
    operation_id="runTravelIntelligenceJob",
)
async def run_travel_intelligence(
    auth: RequireAuthentication,
    job: CurrentTravelIntelligenceJob,
) -> Response:
    trace_id = get_request_id() or ""
    stats = await job.execute()

    envelope = DataEnvelope(data={"status": "completed", "telemetry": stats})
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=envelope.model_dump(mode="json"),
        headers={"X-Request-ID": trace_id},
    )


@router.get(
    "/status",
    response_model=DataEnvelope[list[JobExecutionResponse]],
    status_code=status.HTTP_200_OK,
    summary="List background jobs status and execution telemetry",
    operation_id="listBackgroundJobsStatus",
)
async def list_jobs_status(
    auth: RequireAuthentication,
    scheduler: CurrentJobScheduler,
) -> Response:
    trace_id = get_request_id() or ""
    statuses = scheduler.list_job_statuses()

    items = [
        JobExecutionResponse(
            job_id=s.job_id,
            last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
            next_run_at=s.next_run_at.isoformat() if s.next_run_at else None,
            runs_count=s.runs_count,
            success_count=s.success_count,
            failure_count=s.failure_count,
            last_error=s.last_error,
            is_running=s.is_running,
        )
        for s in statuses
    ]

    envelope = DataEnvelope(data=items)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=envelope.model_dump(mode="json"),
        headers={"X-Request-ID": trace_id},
    )
