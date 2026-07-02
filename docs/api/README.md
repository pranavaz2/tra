# docs/api/ — API Documentation

This folder contains **API contract documentation** for the Travix AI backend.

---

## Purpose

The API documentation defines the contract between the backend (FastAPI) and the frontend
(Flutter) — and any future third-party integrators. It describes available endpoints, request
and response schemas, authentication requirements, error codes, and versioning behavior.

---

## Primary API Documentation

FastAPI auto-generates interactive API documentation from the code:

| Interface | URL (local) | Description |
|---|---|---|
| Swagger UI | `http://localhost:8000/docs` | Interactive API explorer |
| ReDoc | `http://localhost:8000/redoc` | Readable API reference |
| OpenAPI JSON | `http://localhost:8000/openapi.json` | Machine-readable schema |

The auto-generated docs are the **primary reference** for endpoint-level details.
This folder contains supplementary documentation for:

- Authentication flows (token lifecycle, refresh strategy)
- Error response format (RFC 7807 Problem Details)
- Pagination conventions (cursor-based)
- Rate limiting behavior
- Breaking change policy

---

## Contents

This folder will contain:

| Document | Purpose |
|---|---|
| `authentication.md` | JWT flow, refresh token rotation, token revocation |
| `error-format.md` | RFC 7807 Problem Details format used for all errors |
| `pagination.md` | Cursor-based pagination — request params and response shape |
| `rate-limiting.md` | Rate limit tiers and headers |
| `versioning.md` | API versioning policy and upgrade guide |
| `changelog.md` | API-level changelog (breaking changes, new endpoints) |

---

## API Conventions

All Travix AI API endpoints follow these conventions:

- **Base path:** `/api/v1/`
- **Authentication:** Bearer JWT token in `Authorization` header (unless public)
- **Content type:** `application/json`
- **Error format:** RFC 7807 Problem Details (`type`, `title`, `status`, `detail`, `instance`)
- **Pagination:** Cursor-based for all list endpoints
- **Timestamps:** ISO 8601 with UTC timezone (`2025-01-15T10:30:00Z`)

---

## Status

> API documentation will be populated as endpoints are implemented.
> The auto-generated Swagger UI at `/docs` is always the most up-to-date reference.
