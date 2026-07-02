# Authentication API Layer

**Status:** Not yet implemented — placeholder for Sprint 2 / TASK-2.3.

## Purpose

FastAPI routes and Pydantic schemas for the Authentication bounded context.

## Planned files

| File | Purpose |
|---|---|
| `router.py` | FastAPI `APIRouter` — routes only, no business logic |
| `schemas.py` | Pydantic request / response models for auth endpoints |

## Planned endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Create a new user account |
| `POST` | `/api/v1/auth/login` | Authenticate and receive tokens |
| `POST` | `/api/v1/auth/refresh` | Rotate a refresh token |
| `POST` | `/api/v1/auth/logout` | Revoke the current session |
| `POST` | `/api/v1/auth/logout-all` | Revoke all sessions for the current user |
| `POST` | `/api/v1/auth/verify-email` | Mark an email address as verified |

## Constraints (from CLAUDE.md)

- All routes prefixed `/api/v1/`.
- All endpoints have explicit Pydantic request and response models.
- Errors follow RFC 7807 Problem Details format.
- All endpoints require authentication unless annotated otherwise (`register` and `login` are public).
- JWT access tokens: 15-minute maximum lifetime.
- Refresh tokens: 7-day expiry, stored in PostgreSQL.
