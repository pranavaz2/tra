# TASK-2.8 — Registration API: Presentation Layer

**Sprint:** 2 — Identity Context  
**Status:** ✅ Complete  
**Depends on:** TASK-2.7 (RegistrationService)  
**Implemented by:** Claude (Sonnet 4.6)

---

## Objective

Implement the HTTP presentation layer for `POST /api/v1/auth/register`, completing
the vertical slice for user registration. This layer translates between the HTTP
protocol and the domain command/result model. No business logic is introduced here.

---

## Scope

**In scope (this task):**
- `apps/api/app/modules/identity/authentication/presentation/__init__.py`
- `apps/api/app/modules/identity/authentication/presentation/request_context.py`
- `apps/api/app/modules/identity/authentication/presentation/schemas.py`
- `apps/api/app/modules/identity/authentication/presentation/error_responses.py`
- `apps/api/app/modules/identity/authentication/presentation/router.py`
- `apps/api/app/main.py` — router registration
- `apps/api/tests/unit/identity/authentication/test_registration_api.py`

**Out of scope (deferred):**
- Rate limiting enforcement (extension points only)
- Idempotency-Key persistence (header accepted, not stored)
- Login, email verification, OAuth, passkeys endpoints

---

## Architecture

### Request Lifecycle

```
Client
  │
  ▼
POST /api/v1/auth/register
  │
  ├─ RequestIDMiddleware         assigns/propagates X-Request-ID, X-Correlation-ID
  │
  ├─ CORS / Security headers
  │
  ▼
register_user() handler
  │
  ├─ RegisterRequest (Pydantic)  transport validation: presence, max_length, enum
  │
  ├─ get_request_context()       extracts RequestContext: request_id, ip, user_agent,
  │                              locale, timezone, app_version, received_at
  │
  ├─ RegisterUserCommand         built from validated body + RequestContext
  │
  ├─ RegistrationService.execute(command)
  │     ↓ Result[RegistrationSummary]
  │
  ├─ if result.is_ok → False
  │     └─ map_registration_failure() → RFC 7807 JSONResponse
  │
  └─ if result.is_ok → True
        └─ RegisterResponse → DataEnvelope → JSONResponse 201
```

### Sequence Diagram (production — verification required)

```
Client          Router            RegistrationService     EventPublisher
  │                │                      │                    │
  │  POST /register│                      │                    │
  │───────────────►│                      │                    │
  │                │  execute(command)    │                    │
  │                │─────────────────────►│                    │
  │                │                      │  save credential   │
  │                │                      │  push events       │
  │                │                      │─────────────────────►
  │                │                      │  EmailVerificationRequested published
  │                │  Result[Summary]     │                    │
  │                │◄─────────────────────│                    │
  │  201 {         │                      │                    │
  │    requires_   │                      │                    │
  │    verification│                      │                    │
  │    : true      │                      │                    │
  │  }◄────────────│                      │                    │
```

### Sequence Diagram (dev/CI — auto-verified)

```
Client          Router            RegistrationService
  │                │                      │
  │  POST /register│                      │
  │───────────────►│                      │
  │                │  execute(command)    │
  │                │─────────────────────►│
  │                │                      │  credential.verify_email()
  │                │                      │  create session
  │                │                      │  issue access_token + refresh_token
  │                │  Result[Summary]     │
  │                │◄─────────────────────│
  │  201 {         │                      │
  │    requires_   │                      │
  │    verification│                      │
  │    : false,    │                      │
  │    access_token│                      │
  │    refresh_    │                      │
  │    token, ...  │                      │
  │  }◄────────────│                      │
```

---

## Design Decisions

### DD-1: RequestContext as a frozen dataclass dependency

**Alternative considered:** individual `Header(...)` parameters in the route signature.

**Choice:** single `RequestContext` frozen dataclass injected via `Depends(get_request_context)`.

**Rationale:** prevents parameter explosion as new headers are added (Idempotency-Key, A/B
flags, locale). The dependency boundary is clean: the handler receives one context object,
not 7 individual parameters. The `received_at` field (set at dependency resolution time) is
used as the session `created_at` value — accurate to milliseconds.

### DD-2: Presentation layer uses API contract error URIs, not core exception handler URIs

`app/core/exceptions.py` uses `https://travixai.com/errors` as the error type base.
The frozen Authentication API contract specifies `https://errors.travix.ai/auth/<slug>`.

**Choice:** the presentation layer builds RFC 7807 responses directly with the contract URIs.
The global exception handler is bypassed for all known auth errors.

**Rationale:** the API contract is the source of truth for client-visible URIs. Delegating
to the core handler would produce wrong URIs or require the core handler to be
auth-domain-aware (a coupling violation).

### DD-3: `plain_refresh_token.as_client_token()` is the only safe extraction path

`PlainRefreshToken.__repr__` and `__str__` both return `[REDACTED]`. The only way to
obtain the raw token for the HTTP response is `as_client_token()`. The router code
uses this method with an explicit comment explaining the security invariant.

### DD-4: Rate limiting — extension points, no enforcement

Rate limiting is documented (5 req/hr/IP) but not enforced in this task. Three artifacts
define the integration surface:
- `RateLimitInfo` dataclass — carries limit, remaining, reset, retry_after
- `add_rate_limit_headers(headers, info)` — mutates response header dict
- `build_rate_limit_response(trace_id, retry_after_seconds)` — builds 429 JSONResponse

When a Redis-backed rate limiter is added, it plugs into these three functions without
changing the route handler.

### DD-5: Idempotency-Key — documented, not persisted

The header is accepted and echoed. Persistence is deferred to a future task.
Planned implementation: Redis DB 3, key `idempotency:{ip}:{key}`, TTL 86400s,
stores `{status_code, body}`. Repeat requests within TTL return the cached body.

---

## API Contract

### Request

```
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "alice@example.com",      // string, 1–254 chars
  "password": "CorrectHorseBattery!", // string, 1–128 chars
  "device_info": {                    // optional
    "device_name": "Alice's iPhone",  // string, max 100 chars
    "platform": "ios",                // "ios" | "android" | "web"
    "app_version": "1.0.0",          // string, max 20 chars
    "os_version": "iOS 17.4"         // string, max 50 chars
  }
}
```

### Response — 201 (verification required)

```json
{
  "data": {
    "user_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
    "email": "alice@example.com",
    "requires_verification": true,
    "message": "Please check your email to verify your account before logging in."
  }
}
```

### Response — 201 (auto-verified, dev/CI)

```json
{
  "data": {
    "user_id": "b8e3f1a2-4c5d-6e7f-8a9b-0c1d2e3f4a5b",
    "email": "alice@example.com",
    "requires_verification": false,
    "access_token": "eyJ...",
    "refresh_token": "8f14e45f...",
    "token_type": "Bearer",
    "access_token_expires_at": "2026-06-27T00:15:00Z",
    "refresh_token_expires_at": "2026-07-04T00:00:00Z",
    "session": {
      "session_id": "c4d7e9f0-1b2a-3c4d-5e6f-7a8b9c0d1e2f",
      "device_name": null,
      "created_at": "2026-06-27T00:00:00Z"
    }
  }
}
```

### Error Catalogue

| HTTP | `error_code` | Condition |
|------|---|---|
| 409 | `AUTH_EMAIL_ALREADY_EXISTS` | Email already registered |
| 422 | `VALIDATION_ERROR` + `AUTH_EMAIL_INVALID` | Domain rejected email format |
| 422 | `VALIDATION_ERROR` + `AUTH_PASSWORD_TOO_WEAK` | Password fails policy (includes `violations[]`) |
| 422 | `VALIDATION_ERROR` | Transport validation failure (missing field, over max_length) |
| 429 | `AUTH_RATE_LIMITED` | Rate limit exceeded (not yet enforced) |
| 500 | `AUTH_INTERNAL_ERROR` | Unexpected error |
| 503 | `AUTH_SERVICE_UNAVAILABLE` | PasswordHashingError / InfrastructureError |

All errors follow RFC 7807: `type`, `title`, `status`, `detail`, `instance`, `error_code`, `trace_id`.

---

## Threat Model

### T1: Registration Spam / Account Enumeration

**Threat:** attacker submits thousands of registrations to create junk accounts or
enumerate valid email addresses via timing differences.

**Mitigations implemented:**
- 409 response for duplicate email uses a generic message that does not echo the submitted
  email address (prevents enumeration).
- Rate limiting extension points defined (enforcement deferred to TASK-2.x).

**Mitigations deferred:** Redis-backed sliding window rate limiter.

### T2: Password Exfiltration via Logs

**Threat:** plaintext password leaks into structured logs, error messages, or exception
traces and is captured by a logging aggregator.

**Mitigations implemented:**
- Route handler logs only `request_id`, `ip_address`, `user_agent` on receipt.
- On success, logs `requires_verification` and `session_created` — no credentials.
- On failure, logs `error_code` only — not `error.message`.
- `PlainRefreshToken.__str__` and `__repr__` return `[REDACTED]`.
- `as_client_token()` is the only extraction path; its use is commented.

**Fields NEVER logged:** password, password hash, verification token, JWT, refresh token.

### T3: Internal Error Leakage

**Threat:** raw exception messages, stack traces, or internal DB error strings exposed
in 500/503 responses allow attackers to fingerprint infrastructure.

**Mitigations implemented:**
- `map_registration_failure()` for `PasswordHashingError` / `InfrastructureError` returns a
  generic "service temporarily unavailable" message — the original exception message is not
  included.
- The catch-all 500 path returns a generic "unexpected error" message.
- The global `unhandled_exception_handler` in `app/core/exceptions.py` strips tracebacks.

### T4: Malformed / Oversized Requests

**Threat:** attacker sends a 100MB password to trigger algorithmic complexity in the
hashing layer (DoS).

**Mitigations implemented:**
- `password` field has `max_length=128` in Pydantic. Requests exceeding this are rejected
  with 422 before the handler executes.
- `email` field has `max_length=254` (RFC 5321 limit).

### T5: Prompt Injection via Registration Fields

**Threat:** attacker registers with `email = "Ignore all previous instructions..."` hoping
the string is later interpolated into an AI prompt.

**Mitigations implemented (in application layer, not here):**
- Domain Email value object normalises and validates format.
- AI prompt templates (not yet implemented) must receive user data as data values, not
  interpolated into instruction text (CLAUDE.md §11).

### T6: Replay Attacks via Idempotency Key

**Threat:** attacker replays a successful registration request using a stolen Idempotency-Key.

**Current state:** Idempotency-Key is accepted and echoed but not persisted. No replay
risk currently, because each request is re-executed. Once persistence is added, the key
must be scoped to `(ip_address, key)` — not `key` alone — to prevent cross-origin replay.

---

## Self-Review (Principal API Engineer)

### 1. Improvements Over Initial Draft

- Removed 7 implicit header parameters from the route signature by introducing
  `RequestContext` as a single injected dependency — the handler signature dropped from
  9 parameters to 3.
- Error URI base changed from `https://travixai.com/errors` (core exception handler) to
  the correct `https://errors.travix.ai/auth/<slug>` (API contract).
- Added `RateLimitInfo`, `add_rate_limit_headers()`, `build_rate_limit_response()` as
  typed extension points — rate limiting integration requires no handler changes.
- `received_at` added to `RequestContext` and used as session `created_at`, avoiding a
  clock call inside the handler (which would be after the UoW commit, adding drift).

### 2. API Design Decisions

- `requires_verification` boolean in the 201 body — eliminates the "am I in prod or dev?"
  ambiguity. The client branches on this field, not on token presence.
- `email` in the response body is the server-normalised value (lowercase, stripped).
  Clients display this value, not the raw user input.
- `DataEnvelope[T]` wraps all success responses in `{ "data": ... }` per API contract §3.1.
- All error responses are `JSONResponse` built directly, not via `HTTPException`, to
  preserve RFC 7807 shape without the default FastAPI error format.

### 3. Request Lifecycle

Request enters `RequestIDMiddleware` → assigns UUID request_id, propagates correlation_id
via ContextVars → hits the router → Pydantic validates body → `get_request_context()`
extracts headers and `datetime.now(UTC)` → handler builds `RegisterUserCommand` → calls
`RegistrationService.execute()` → maps `Result[RegistrationSummary]` → returns
`JSONResponse` with `X-Request-ID` header.

### 4. Threat Model Summary

Five threats addressed at the presentation layer (T1–T4, T6). T5 (prompt injection) is
addressed in the application/AI layer. The highest residual risk is registration spam
(T1) — the rate limiter is the next priority.

### 5. Performance Considerations

- The handler is `async def` and performs no I/O itself — it delegates entirely to the
  application service, which is already async.
- `get_settings()` is called once per request in the success path to read JWT expiry
  config. This is a cached Pydantic `BaseSettings` object — effectively free.
- `RequestContext` construction is in a dependency, not the handler body, so it runs in
  the DI resolution phase — no observable latency impact.

### 6. Remaining TODOs

| Priority | Item |
|---|---|
| High | TASK-2.9: Redis-backed rate limiter (5 req/hr/IP) |
| High | TASK-2.10: Email verification endpoint (`POST /verify-email`) |
| Medium | TASK-2.11: Idempotency-Key persistence (Redis DB 3, 24h TTL) |
| Medium | TASK-2.12: Login endpoint (`POST /login`) |
| Low | TASK-2.x: OpenAPI examples with realistic JWT strings |

### 7. Future Impact

**Login endpoint** (`POST /login`): the same `RequestContext`, `DataEnvelope`, and error
response pattern apply directly. The `SessionResponse` schema is shared.

**Email Verification** (`POST /verify-email`): `RequestContext` is reused unchanged.
The 422 → 409 → 200 error shape follows the same pattern.

**OAuth** (`POST /auth/oauth/callback`): a new `OAuthCallbackRequest` schema, but the
same `DataEnvelope` and `map_auth_failure()` helper pattern.

**Passkeys** (`POST /auth/passkey/register`): same layering; no changes to this module.

**Flutter Integration**: the `RegisterResponse` schema drives the Dart data model. The
`requires_verification` flag is the branch point in the Flutter registration flow.
Store `refresh_token` in Flutter Secure Storage, `access_token` in memory only.

---

## Definition of Done

- [x] Implementation matches task specification
- [x] All functions have type hints
- [x] `ruff check` passes with zero violations
- [x] `black --check` passes
- [x] No business logic in the presentation layer
- [x] All external service calls go through the abstraction layer
- [x] Module boundaries respected
- [x] Naming conventions followed (Section 8, CLAUDE.md)
- [x] All routes prefixed `/api/v1/`
- [x] All endpoints have Pydantic request and response models
- [x] Error responses follow RFC 7807 Problem Details format
- [x] Authentication applied (not applicable — this IS the registration endpoint)
- [x] No secrets or credentials in any committed file
- [x] No `os.environ` usage in application code
- [x] User input validated at the API boundary
- [x] Unit tests written and passing (test_registration_api.py)
- [x] AI provider not involved — no mock needed
- [x] Task specification (this file) complete
