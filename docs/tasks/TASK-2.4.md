# TASK-2.4 — Identity Context: Authentication API Contract

**Status:** Complete
**Phase:** 2 — Sprint 2
**Depends on:** TASK-2.3 (Password Hashing Infrastructure)
**Blocks:** TASK-2.5 (Registration Implementation), TASK-2.6 (Login Implementation)

---

## Objective

Design the complete, stable Authentication API contract for Travix AI.
No implementation. This contract is the source of truth for all future
authentication endpoint implementations.

The contract must remain stable for the v1 lifetime. Breaking changes
require a v2 prefix and client migration documentation.

---

## Scope

### In Scope

- All 12 authentication endpoints (request schema, response schema, errors,
  validation rules, rate limits, idempotency, examples)
- Standard response envelope (success, error, validation error, async accepted)
- Authentication token lifecycle documentation
- Rate limiting strategy table
- Complete error catalogue (28 error codes)
- Security considerations (CSRF, replay, enumeration, timing, storage)
- Future authentication method compatibility (OAuth, Passkeys, Magic Links)
- Flow diagrams (5 Mermaid sequence diagrams)
- OpenAPI readiness mapping

### Explicitly Out of Scope

- FastAPI implementation
- Pydantic schemas (TASK-2.5)
- JWT implementation (TASK-2.5/2.6)
- Database models or migrations
- Dependency injection
- Business logic

---

## Deliverables

| File | Description |
|---|---|
| `docs/api/authentication.md` | Complete API contract |
| `docs/tasks/TASK-2.4.md` | This file |

---

## API Design Principles Applied

### 1. Enumeration Prevention

Three endpoints always return the same response regardless of whether the
email address exists in the system:

- `POST /login` — `AUTH_INVALID_CREDENTIALS` for both wrong email and wrong password
- `POST /forgot-password` — always 202 Accepted
- `POST /resend-verification` — always 202 Accepted

Timing equalization is enforced at the service layer (password hash always
runs to prevent timing side-channels).

### 2. Refresh Token Rotation

Every `POST /refresh` call:
1. Marks the submitted refresh token as superseded.
2. Issues a new refresh token.
3. Returns both new access token and new refresh token.

Reuse of a superseded token revokes the entire token family immediately.
This is the primary stolen-token detection mechanism (see ADR-003).

### 3. Registration Auto-Login Gating

`POST /register` returns `requires_verification: bool`.

- When `true` (production): no tokens in response; user must verify email.
- When `false` (CI/test): tokens issued immediately.

This single field allows clients to handle both modes without branching on
environment-specific logic.

### 4. Password Reset Auto-Login

`POST /reset-password` returns authentication tokens on success. The user is
immediately authenticated after resetting. This eliminates the unnecessary
login round-trip after a reset and aligns with the UX of every major consumer app.

### 5. Consistent Token Response Shape

`POST /login`, `POST /refresh`, `POST /reset-password`, and `POST /verify-email`
all return the same token response shape. Future authentication methods (OAuth,
Passkeys, Magic Links) are required to use this same shape.

### 6. Device Info Optional

Login accepts optional `device_info` (device_name, platform, app_version,
os_version). This enables "Alice's iPhone 15" session display without making
device reporting mandatory. Clients that don't support it degrade gracefully.

### 7. Logout Idempotency

`POST /logout` is idempotent. Calling logout on an already-revoked session
has no error. Clients should delete tokens locally BEFORE calling logout,
then navigate to the login screen regardless of the API response. This prevents
stuck states caused by network failures.

---

## Error Catalogue Summary

28 error codes defined, covering:

- Input validation: email format, password strength, password reuse
- Account state: disabled, locked, email not verified, password expired
- Token state: missing, malformed, invalid, expired, revoked
- Refresh token: invalid, expired, revoked, reuse detected
- Session: not found, expired, revoked, max exceeded
- Password reset tokens: invalid, expired, already used
- Verification tokens: invalid, expired, already verified
- Rate limiting

---

## Security Audit Points for Implementation

The following security-critical behaviors are specified in the contract and
must be verified during implementation review:

- [ ] `POST /login` returns identical error for wrong email and wrong password
- [ ] Password verification never short-circuits before constant-time compare
- [ ] `POST /forgot-password` runs the full pipeline (including timing equalization) even when email doesn't exist
- [ ] Reset tokens are stored as SHA-256 hashes, never in plaintext
- [ ] Verification tokens are stored as SHA-256 hashes, never in plaintext
- [ ] Refresh token reuse revokes the ENTIRE family (not just the submitted token)
- [ ] `POST /refresh` rotation is atomic: old token superseded before new token issued
- [ ] All access token revocations go through Redis (not only PostgreSQL)
- [ ] Account lockout is enforced before password verification (prevents timing oracle)

---

## Rate Limiting Implementation Notes

Rate limiting is applied via middleware using Redis (DB 3 — rate_limit).
Sliding window counters. Keys expire automatically.

Key formats:
- Per-email: `rate:auth:{endpoint}:email:{sha256_of_email}`
- Per-IP: `rate:auth:{endpoint}:ip:{ip_address}`
- Per-user: `rate:auth:{endpoint}:user:{user_id}`
- Per-token-family: `rate:auth:refresh:family:{family_id}`

`sha256_of_email` is used (not raw email) to avoid storing PII in Redis keys.

---

## Future Compatibility Checklist

The contract explicitly reserves paths for:

- [ ] OAuth 2.0: `GET /auth/oauth/{provider}/authorize`, `POST /auth/oauth/{provider}/callback`
- [ ] Passkeys: `POST /auth/passkey/registration/{begin,complete}`, `POST /auth/passkey/authentication/{begin,complete}`
- [ ] Magic Links: `POST /auth/magic-link/request`, `POST /auth/magic-link/verify`
- [ ] JWKS: `GET /auth/.well-known/jwks.json` (per ADR-003 RS256 migration)

All future methods MUST return the same token response shape as `POST /login`.

---

## Definition of Done

- [x] All 12 endpoints have complete request schema with field-level validation rules
- [x] All 12 endpoints have complete response schema with example JSON
- [x] All 12 endpoints list every possible error response
- [x] Error catalogue has 28 codes with HTTP status, title, and detail
- [x] Standard response envelope (success, error, validation, async) documented
- [x] Token lifecycle documented (JWT claims, rotation, revocation, storage)
- [x] Rate limiting table covers all endpoints
- [x] Security considerations documented (CSRF, replay, enumeration, timing, storage)
- [x] Enumeration prevention strategy documented for all applicable endpoints
- [x] 5 Mermaid sequence diagrams (registration, login, refresh, logout, reset)
- [x] Future authentication methods (OAuth, Passkeys, Magic Links) reserved
- [x] OpenAPI readiness section maps all schemas and response codes
- [x] Frontend developer notes for every endpoint
- [x] Error type URIs defined (`https://errors.travix.ai/auth/...`)
