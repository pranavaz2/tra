"""API endpoint tests for Trip Export (iCal and PDF) router."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.security.auth.context import AuthorizationContext
from app.core.security.auth.dependencies import get_authorization_context
from app.modules.travel.export.application.export_service import ExportService
from app.modules.travel.export.infrastructure.dependencies import get_export_service
from app.modules.travel.export.presentation.router import router as export_router
from app.shared.domain.errors import ForbiddenError, NotFoundError
from app.shared.domain.result import Failure, Success


from datetime import UTC, datetime, timedelta


def create_auth_context(user_id: str) -> AuthorizationContext:
    now = datetime.now(UTC)
    return AuthorizationContext(
        user_id=user_id,
        session_id=str(uuid.uuid4()),
        token_id=str(uuid.uuid4()),
        token_version=1,
        session_version=1,
        authentication_method="password",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        email="test@example.com",
        is_email_verified=True,
    )


@pytest.mark.asyncio
async def test_export_ical_api_success():
    """Verify GET /api/v1/trips/{trip_id}/export/ical returns 200 with text/calendar Content-Type."""
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    mock_service = MagicMock(spec=ExportService)
    ics_payload = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Travix AI//EN\r\nEND:VCALENDAR\r\n"
    mock_service.export_ical = AsyncMock(return_value=Success(ics_payload))

    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")
    app.dependency_overrides[get_export_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{trip_id}/export/ical")

    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert response.text == ics_payload


@pytest.mark.asyncio
async def test_export_pdf_api_success():
    """Verify GET /api/v1/trips/{trip_id}/export/pdf returns 200 with application/pdf Content-Type."""
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    mock_service = MagicMock(spec=ExportService)
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
    mock_service.export_pdf = AsyncMock(return_value=Success(pdf_bytes))

    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")
    app.dependency_overrides[get_export_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{trip_id}/export/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert response.content == pdf_bytes


@pytest.mark.asyncio
async def test_export_ical_forbidden():
    """Verify GET /api/v1/trips/{trip_id}/export/ical returns 403 when user is not a member."""
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    mock_service = MagicMock(spec=ExportService)
    mock_service.export_ical = AsyncMock(
        return_value=Failure(ForbiddenError("Access denied: Not a member of this trip."))
    )

    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")
    app.dependency_overrides[get_export_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{trip_id}/export/ical")

    assert response.status_code == 403
    data = response.json()
    assert "Access denied" in data["detail"]


@pytest.mark.asyncio
async def test_export_pdf_not_found():
    """Verify GET /api/v1/trips/{trip_id}/export/pdf returns 404 when trip is not found."""
    user_id = str(uuid.uuid4())
    trip_id = str(uuid.uuid4())

    mock_service = MagicMock(spec=ExportService)
    mock_service.export_pdf = AsyncMock(
        return_value=Failure(NotFoundError("Trip not found"))
    )

    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")
    app.dependency_overrides[get_export_service] = lambda: mock_service
    app.dependency_overrides[get_authorization_context] = lambda: create_auth_context(user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/trips/{trip_id}/export/pdf")

    assert response.status_code == 404
