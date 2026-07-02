# TASK-2.6 — Identity Context: Refresh Token Infrastructure

**Status:** Complete
**Phase:** 2 — Sprint 2
**Depends on:** TASK-2.5 (JWT Infrastructure)
**Blocks:** TASK-2.7 (Login Implementation), TASK-2.8 (Registration Implementation)

---

## Objective

Implement the production-grade Refresh Token subsystem for Travix AI. This is
infrastructure only — no login, no registration, no FastAPI routes, no business logic.

The output is a complete refresh token lifecycle system that the authentication
application layer (TASK-2.7+) can inject and use without knowing anything about
token generation algorithms, hash functions, or store implementations.

---

## Scope

### In Scope

- `PlainRefreshToken` value object (256-bit opaque, URL-safe, `[REDACTED]` repr)
- `RefreshTokenHash` value object (SHA-256 hex, 64 chars, validated on construction)
- `TokenState` enum (ACTIVE → ROTATED / EXPIRED / REVOKED)
- `RefreshTokenRecord` entity with full lifecycle (create, mark_rotated, mark_expired, revoke)
- New domain events: `RefreshTokenReuseDetected`, `SessionRevokedDueToTokenReuse`
- New domain errors: `RefreshTokenNotFoundError`, `RefreshTokenExpiredError`, `RefreshTokenRevokedError`
- `RefreshTokenRepository` Protocol (domain repository interface with `rotate()` atomicity contract)
- `RefreshTokenGenerator` and `RefreshTokenHasher` domain service Protocols
- `AuthenticationSession.revoke_due_to_token_reuse()` mutation method
- Application interfaces: `RefreshTokenService`, `SessionRevocationService`, `TokenRevocationService`
- `SecureRefreshTokenGenerator` (infrastructure: `secrets.token_urlsafe(32)`)
- `Sha256RefreshTokenHasher` (infrastructure: `hashlib.sha256`)
- `InMemoryRefreshTokenStore` (infrastructure: dev/test, `asyncio.Lock` atomicity)
- `InMemorySessionRepository` (infrastructure: dev/test placeholder for TASK-2.7)
- `RefreshTokenApplicationService` (application: orchestrates full lifecycle)
- DI registration for all services in `infrastructure/dependencies.py`
- Comprehensive unit tests (14 test classes, 50+ test cases)

### Explicitly Out of Scope

- Login endpoint implementation
- Registration endpoint implementation
- Refresh endpoint implementation (`POST /api/v1/auth/refresh`)
- Redis-backed TokenRevocationService (JTI blacklist)
- PostgreSQL-backed RefreshTokenRepository
- Database migrations for refresh_token_records table
- Auth middleware

---

## Files Created / Modified

### Created

| File | Description |
|---|---|
| `app/modules/identity/authentication/domain/value_objects/plain_refresh_token.py` | `PlainRefreshToken` — 256-bit opaque token with `[REDACTED]` repr |
| `app/modules/identity/authentication/domain/value_objects/refresh_token_hash.py` | `RefreshTokenHash` — SHA-256 hex value object with construction validation |
| `app/modules/identity/authentication/domain/entities/refresh_token_record.py` | `RefreshTokenRecord` entity + `TokenState` enum |
| `app/modules/identity/authentication/domain/services/refresh_token_protocols.py` | `RefreshTokenGenerator` and `RefreshTokenHasher` domain Protocols |
| `app/modules/identity/authentication/application/refresh_token_service.py` | `RefreshTokenApplicationService` |
| `app/modules/identity/authentication/infrastructure/refresh_token_generator.py` | `SecureRefreshTokenGenerator` |
| `app/modules/identity/authentication/infrastructure/refresh_token_hasher.py` | `Sha256RefreshTokenHasher` |
| `app/modules/identity/authentication/infrastructure/refresh_token_store.py` | `InMemoryRefreshTokenStore` + `InMemorySessionRepository` |
| `tests/unit/identity/authentication/test_refresh_token_infrastructure.py` | Comprehensive unit tests |
| `docs/tasks/TASK-2.6.md` | This file |
| `docs/adr/ADR-005-refresh-token-lifecycle-and-rotation.md` | Architecture Decision Record |

### Modified

| File | Change |
|---|---|
| `app/modules/identity/authentication/domain/events/authentication_events.py` | Added `RefreshTokenReuseDetected`, `SessionRevokedDueToTokenReuse` |
| `app/modules/identity/authentication/domain/errors.py` | Added `RefreshTokenNotFoundError`, `RefreshTokenExpiredError`, `RefreshTokenRevokedError` |
| `app/modules/identity/authentication/domain/repositories/interfaces.py` | Added `RefreshTokenRepository` Protocol with `rotate()` atomicity contract |
| `app/modules/identity/authentication/domain/entities/session.py` | Added `revoke_due_to_token_reuse()` mutation method |
| `app/modules/identity/authentication/application/interfaces.py` | Added `RefreshTokenService`, `SessionRevocationService`, `TokenRevocationService` Protocols |
| `app/modules/identity/authentication/infrastructure/dependencies.py` | Added DI for generator, hasher, store, session repo, and application service |

---

## Architecture

### Token Anatomy

```
Client receives:       PlainRefreshToken.value       (256-bit URL-safe string, never stored)
Database stores:       RefreshTokenRecord.token_hash (SHA-256 hex, 64 chars)
Session references:    AuthenticationSession.refresh_token_id (UUID → RefreshTokenId)
```

### Layer Responsibilities

```
domain/value_objects/   PlainRefreshToken, RefreshTokenHash    pure value objects
domain/entities/        RefreshTokenRecord                      lifecycle state machine
domain/services/        RefreshTokenGenerator, RefreshTokenHasher  crypto contracts
domain/repositories/    RefreshTokenRepository                  persistence contract
application/            RefreshTokenApplicationService          orchestration
infrastructure/         SecureRefreshTokenGenerator             CSPRNG implementation
                        Sha256RefreshTokenHasher                SHA-256 implementation
                        InMemoryRefreshTokenStore               dev/test store
                        InMemorySessionRepository               dev/test session store
```

### Token Lifecycle

```
                  PlainRefreshToken.generate()
                         │
                         ▼
              Sha256RefreshTokenHasher.hash()
                         │
                         ▼
              RefreshTokenRecord.create(token_hash=..., status=ACTIVE)
                         │
              ┌──────────┴──────────────────────┐
              │                                  │
          rotate()                          revoke()
              │                                  │
              ▼                                  ▼
   ACTIVE → ROTATED + new ACTIVE           ACTIVE → REVOKED
              │
   (present ROTATED token again)
              │
              ▼
   REUSE DETECTED → revoke entire session
```

### Session State Machine

```
   ACTIVE ──── (explicit logout) ─────────→ REVOKED
      │
      ├──── (TTL elapsed) ──────────────→ EXPIRED
      │
      └──── (token reuse detected) ─────→ REVOKED (via revoke_due_to_token_reuse)
```

### Rotation Flow

```
Client → POST /auth/refresh (token: "abc123...")
              │
              ▼ hash
SHA-256("abc123...") = "a1b2c3..."
              │
              ▼ lookup
RefreshTokenRepository.find_by_hash("a1b2c3...")
              │
              ├── None → RefreshTokenNotFoundError (401)
              ├── ROTATED → RefreshTokenReuseError (401) + session revocation
              ├── REVOKED → RefreshTokenRevokedError (401)
              ├── EXPIRED → RefreshTokenExpiredError (401)
              └── ACTIVE → validate session → atomic rotate → return new token
```

---

## Security Architecture

### 1. Token Generation

`secrets.token_urlsafe(32)` produces 32 bytes from `os.urandom()` (or the OS CSPRNG),
URL-safe base64 encoded. Result: 43 characters, 256 bits of entropy.

No UUIDs. No sequential IDs. Not guessable. Not reversible.

### 2. Hash Storage

SHA-256 is the right algorithm here (not Argon2id/bcrypt):
- The token has 256 bits of pre-existing entropy — dictionary attacks are infeasible.
- SHA-256 is a one-way function; the token cannot be recovered from the hash.
- Argon2id/bcrypt are designed for LOW-ENTROPY inputs (passwords). Applying them
  to high-entropy tokens wastes CPU without adding security.

### 3. Atomic Rotation

The `RefreshTokenRepository.rotate()` method is the critical section:
- In-memory: `asyncio.Lock` prevents concurrent rotations in the same event loop.
- PostgreSQL (future): `SELECT ... FOR UPDATE` within a single transaction.

Any concurrent attempt to rotate an already-ROTATED token fails with
`RefreshTokenReuseError`. This prevents the "double-spend" attack.

### 4. Reuse Detection

If a ROTATED token is presented:
1. `RefreshTokenApplicationService` detects `status == ROTATED`.
2. Calls `_handle_token_reuse()` which:
   - Revokes all tokens for the session via `revoke_all_for_session()`.
   - Calls `session.revoke_due_to_token_reuse()` on the `AuthenticationSession`.
   - Domain events `RefreshTokenReuseDetected` + `SessionRevokedDueToTokenReuse` are pushed.
3. Returns `Failure(RefreshTokenReuseError)`.

### 5. No Plaintext Storage Guarantee

- `PlainRefreshToken.__repr__` → `"PlainRefreshToken([REDACTED])"`
- `PlainRefreshToken.__str__` → `"[REDACTED]"`
- f-strings with a `PlainRefreshToken` variable produce `[REDACTED]`
- The store's `_by_hash` dict is keyed by hash.value (hex string), never by token.value
- Test `test_sha256_storage_verification` verifies plaintext never appears in store internals.

### 6. Device Awareness (No Fingerprinting)

`RefreshTokenRecord` stores `device_id`, `device_name`, and `platform` as client-reported
string fields. The server does NOT:
- Compute device fingerprints.
- Block or challenge based on device mismatch.
- Compare device fields across rotation (informational only).

These fields exist for audit log richness and future anomaly detection. A security policy
that blocks on device mismatch would be a future application-layer decision.

---

## Threat Model

### Attacks Mitigated

| Attack | Mitigation |
|---|---|
| Refresh token theft + replay | One-time use (ROTATED detection); reuse revokes entire session |
| Dictionary / brute-force | 256-bit entropy; SHA-256 hash with no iteration needed |
| Database compromise | Only SHA-256 hashes stored; plaintext unrecoverable |
| Concurrent rotation race ("double-spend") | `asyncio.Lock` in InMemoryStore; DB `FOR UPDATE` in production |
| Token enumeration | URL-safe base64 tokens are not sequential or guessable |
| Cross-type confusion with JWT | Refresh tokens are NOT JWTs; they cannot be used as access tokens |
| Log leakage of token value | `__repr__` and `__str__` always return `[REDACTED]` |

### Out of Scope (Deferred)

| Attack | Status |
|---|---|
| Redis flush causes JTI revocation loss | Mitigated by Redis AOF persistence (documented, not yet enforced) |
| Multi-process concurrent rotation | InMemoryStore is single-process; PostgreSQL + `FOR UPDATE` needed |
| Token theft via MITM | HTTPS enforcement (infrastructure layer, not application layer) |
| Refresh token exfiltration from iOS Secure Enclave | Mobile storage security (Flutter Secure Storage, TASK-3.x) |
| Account takeover via device_id spoofing | Device fields are informational only; no security decisions made on them |

### Security Assumptions

1. The server process is single-threaded from the perspective of `asyncio.Lock`.
   Multi-process deployments MUST replace `InMemoryRefreshTokenStore` with
   PostgreSQL-backed `FOR UPDATE` transactions.

2. `os.urandom()` (via `secrets.token_urlsafe`) is seeded by the OS with sufficient
   entropy. This holds for all modern Linux/macOS/Windows kernel versions.

3. SHA-256 remains collision-resistant for the foreseeable future. If a break is
   announced, switch to SHA-3-256 by changing `Sha256RefreshTokenHasher` only
   (all callers use the `RefreshTokenHasher` Protocol).

4. Clients do NOT send concurrent /auth/refresh requests with the same token.
   Well-behaved mobile apps serialize token refresh. If they do race, the second
   request fails with `RefreshTokenReuseError` and the client must re-authenticate.

5. Server clocks are monotonic and accurate to within the `jwt_leeway_seconds`
   window. Token expiry checks use `datetime.now(UTC)`.

### Future Hardening

- **HMAC-SHA256 for token hashing**: If the database is compromised, an attacker
  could enumerate token hashes against a rainbow table of 43-char URL-safe strings.
  Using `HMAC-SHA256(key=TOKEN_HASH_SECRET, msg=token)` prevents this — but requires
  managing a new secret. For 256-bit random tokens, SHA-256 alone is already safe.

- **Short-lived refresh tokens with sliding expiry**: Rotate expiry on each use
  (already easy to add — update `expires_at` in `rotate()`).

- **Anomaly detection on device_id**: Alert if the same session is used from
  multiple different `device_id` values within a short time window.

---

## Definition of Done

### Code Quality
- [x] All functions and class attributes have type hints
- [x] No `os.environ` usage — all config via `get_settings()`
- [x] No secrets in any source file

### Architecture
- [x] No business logic in Flutter (N/A — backend only)
- [x] All external service calls go through abstraction layer
- [x] Module boundaries respected — no circular imports
- [x] Naming conventions followed (Section 8 of CLAUDE.md)
- [x] Domain layer has zero infrastructure dependencies
- [x] Application service depends only on Protocol interfaces

### Security
- [x] Opaque tokens: NOT JWTs, NOT UUIDs
- [x] 256-bit entropy: `secrets.token_urlsafe(32)`
- [x] No plaintext storage: only SHA-256 hash stored
- [x] Atomic rotation: `asyncio.Lock` in InMemoryStore; contract documented for PostgreSQL
- [x] Reuse detection: ROTATED token → entire session revoked
- [x] `PlainRefreshToken.__repr__` and `__str__` return `[REDACTED]`
- [x] Device awareness: fields stored, no fingerprinting

### Tests
- [x] Unit tests: 50+ cases across 14 test classes
- [x] SHA-256 storage verification (plaintext not in store)
- [x] Atomic rotation (concurrent rotation — only one succeeds)
- [x] Reuse detection (ROTATED token triggers session revocation)
- [x] All error paths (expired, revoked, not found, session expired, session revoked)
- [x] Session lifecycle transitions after rotation

### Documentation
- [x] TASK-2.6.md (this file)
- [x] ADR-005 (refresh token strategy, rotation, reuse detection)

---

## Security Review Notes (Principal Security Engineer)

### Improvements vs. Naive Implementation

1. **ROTATED vs. REVOKED states separated**: A ROTATED token means "used exactly
   once and superseded" — this is the reuse detection sentinel. A REVOKED token
   means "explicitly revoked by user or admin." Conflating these would lose the
   ability to distinguish legitimate token cycling from stolen-token replay.

2. **Lock acquired BEFORE state check in `rotate()`**: The `InMemoryRefreshTokenStore`
   re-validates the record state UNDER the lock. The pre-lock check is an optimization
   for fast failure. The post-lock check is the authoritative one. This pattern
   prevents TOCTOU (time-of-check to time-of-use) races.

3. **`revoke_due_to_token_reuse()` is distinct from `revoke()`**: The domain emits
   different events for security-driven revocation vs. user-driven logout. Security
   monitoring consumers need to distinguish these. `UserLoggedOut` ≠
   `SessionRevokedDueToTokenReuse`.

4. **Session update AFTER atomic token swap, not before**: If the session update
   fails, the new token exists but the session's pointer is stale. This is
   documented and the new token is revoked in that case. In production, both
   operations must be in the same DB transaction.

5. **`_handle_token_reuse()` is best-effort**: Reuse detection triggers aggressive
   revocation, but if the revocation sweep itself fails (DB outage), we still
   return `RefreshTokenReuseError` to the client. The client is refused
   immediately; cleanup is best-effort. This is the correct security posture.

### Remaining TODOs

- [ ] PostgreSQL `RefreshTokenRepository` with `SELECT FOR UPDATE` (TASK-2.7+)
- [ ] Alembic migration for `refresh_token_records` table (TASK-2.7+)
- [ ] `POST /api/v1/auth/refresh` route (TASK-2.7+)
- [ ] `TokenRevocationService` Redis implementation for JTI blacklist
- [ ] Integrate `RefreshTokenService` into login and registration services
- [ ] Background cleanup job: sweep EXPIRED tokens older than N days
