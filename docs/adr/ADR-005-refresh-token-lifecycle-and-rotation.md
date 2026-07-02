# ADR-005 — Refresh Token Lifecycle, Rotation, Reuse Detection, and Revocation

**Status:** Accepted
**Date:** 2026-06-26
**Deciders:** Engineering team
**Technical story:** TASK-2.6 — Identity Context: Refresh Token Infrastructure

---

## Context and Problem Statement

Travix AI issues short-lived JWT access tokens (15 minutes) and long-lived refresh tokens
(7 days). We need a refresh token strategy that:

1. Enables clients to obtain new access tokens without re-authenticating.
2. Detects stolen tokens (if an attacker has a token, we can tell when they use it).
3. Supports explicit revocation (logout, password change, account compromise response).
4. Maintains atomicity — two concurrent refresh requests with the same token must not
   both succeed.
5. Does not store any token value in plaintext.

---

## Decision

### Token Format: Opaque 256-bit URL-safe string (NOT JWT)

Refresh tokens are opaque random strings generated with `secrets.token_urlsafe(32)`:
- 32 bytes = 256 bits of entropy from `os.urandom()`.
- URL-safe base64 encoded: 43 characters, no padding, safe for HTTP headers and cookies.
- Not a JWT — no structure, no signature, no claims. Just random bytes.

**Rejected alternative: UUIDs as refresh tokens**
UUIDs (v4) carry only 122 bits of entropy and are recognisable as UUIDs. 256 bits
provides a larger safety margin against any future advances in random oracle attacks.

**Rejected alternative: Signed JWTs as refresh tokens**
A refresh-token JWT could be validated without a database lookup. However:
- It cannot be revoked without a revocation list (same overhead as the hash lookup).
- A refresh token that leaks from the database exposes its claims.
- An opaque token + database lookup is simpler, more auditable, and supports
  immediate revocation without any Redis coordination.

### Storage: SHA-256 hash only

Only `SHA-256(token)` is stored in the database. The plaintext token is returned
to the client once and never persisted.

**Rejected alternative: Argon2id / bcrypt for refresh token hashing**
Argon2id and bcrypt are designed for LOW-ENTROPY inputs (passwords) where dictionary
attacks are feasible. A 256-bit random token is not susceptible to dictionary attacks;
the 2^256 search space makes precomputation tables impossible. SHA-256 is sufficient and
orders of magnitude faster. Using Argon2id here would waste CPU without adding security.

### Rotation Strategy: One-time use with atomic swap

Every `/auth/refresh` call MUST:
1. Validate the presented token (active, not expired, session valid).
2. Generate a new token.
3. In a single atomic operation: mark the old token as ROTATED, insert the new as ACTIVE.
4. Return the new token.

The old token becomes immediately invalid. The client MUST use the new token for the next
refresh. This is "refresh token rotation."

**Why one-time use matters:**
If an attacker steals a refresh token and the legitimate user also holds it, one-time
use ensures only one can succeed — the other triggers reuse detection.

### Reuse Detection: ROTATED state as stolen-token sentinel

`RefreshTokenRecord.status` transitions:

```
ACTIVE → ROTATED   (token used; replaced by new token)
ACTIVE → EXPIRED   (TTL elapsed)
ACTIVE → REVOKED   (explicit revocation)
ROTATED → REVOKED  (revocation sweep)
EXPIRED → REVOKED  (cleanup sweep)
```

ROTATED, EXPIRED, REVOKED are terminal.

When a client presents a token whose record is ROTATED:
1. This means the token was already used once and superseded.
2. Either the legitimate client sent a stale request, OR an attacker is replaying
   a stolen token.
3. **Response**: Revoke the entire session immediately. Return 401.

This is conservative but secure. False positives (client sent stale token due to a
retry) are acceptable — the user re-authenticates. False negatives (stolen token
not detected) are not acceptable.

### Session Lifecycle States

Sessions (`AuthenticationSession`) have their own state:

```
ACTIVE  — valid, not expired, not revoked
EXPIRED — TTL elapsed (lazy detection)
REVOKED — explicit: logout / security action (revoke_due_to_token_reuse)
```

A REVOKED session rejects all token rotation attempts for that session.

`revoke_due_to_token_reuse()` on `AuthenticationSession`:
- Sets `revoked_at`.
- Emits `RefreshTokenReuseDetected` (for security audit and alerting).
- Emits `SessionRevokedDueToTokenReuse` (distinct from `UserLoggedOut`).

### Atomicity: asyncio.Lock (dev/test) → SELECT FOR UPDATE (production)

The rotate operation's critical invariant: only one concurrent request can successfully
rotate a given refresh token.

**InMemoryRefreshTokenStore (dev/test):**
`asyncio.Lock` is acquired for the entire validate-rotate-insert sequence. A concurrent
request sees the ROTATED state under the lock and receives `RefreshTokenReuseError`.

**PostgreSQL (production — TASK-2.7+):**
```sql
BEGIN;
SELECT * FROM refresh_token_records
WHERE token_hash = $1
FOR UPDATE;           -- exclusive lock on this row

-- validate status = 'active' and not expired
-- if not → ROLLBACK and raise appropriate error
-- if yes → UPDATE to 'rotated', INSERT new record as 'active'
COMMIT;
```

Alternatively, a `SERIALIZABLE` transaction with optimistic retry. Both prevent the
double-spend race condition.

### Device Awareness

`RefreshTokenRecord` stores `device_id`, `device_name`, and `platform`:
- Client-reported strings only.
- The server does NOT compute fingerprints or block based on device mismatch.
- These fields exist for audit logging and future anomaly detection.

Fingerprinting-based blocking is explicitly rejected: it creates false positives for
users with VPNs, corporate proxies, or network address changes, which are common on
mobile devices.

---

## Sequence Diagrams

### Successful Token Rotation

```
Client              API                       RefreshTokenRepository    SessionRepository
  │                  │                                │                       │
  │─── POST /auth/refresh ──▶│                        │                       │
  │    (refresh_token: "abc") │                        │                       │
  │                  │        SHA-256("abc") = "a1b2" │                       │
  │                  │───── find_by_hash("a1b2") ────▶│                       │
  │                  │◀──── record (ACTIVE) ──────────│                       │
  │                  │                                │                       │
  │                  │──── find_by_id(session_id) ───────────────────────────▶│
  │                  │◀─── session (ACTIVE) ─────────────────────────────────│
  │                  │                                │                       │
  │                  │  generate new_token = "xyz"    │                       │
  │                  │  SHA-256("xyz") = "x9y8"       │                       │
  │                  │                                │                       │
  │                  │── rotate(old="a1b2", new=...) ▶│                       │
  │                  │    [LOCK]                       │                       │
  │                  │    old.status = ROTATED         │                       │
  │                  │    insert new (ACTIVE)          │                       │
  │                  │    [UNLOCK]                     │                       │
  │                  │◀── OK ─────────────────────────│                       │
  │                  │                                │                       │
  │                  │── session.rotate_refresh_token(new_record_id) ─────────▶│
  │                  │◀── Success ───────────────────────────────────────────│
  │                  │── save(session) ──────────────────────────────────────▶│
  │                  │                                │                       │
  │◀── 200 OK ───────│                                │                       │
  │  access_token,   │                                │                       │
  │  refresh_token   │                                │                       │
  │  = "xyz"         │                                │                       │
```

### Stolen Token Reuse Detection

```
Attacker            API                      RefreshTokenRepository   SessionRepository
  │                  │                               │                      │
  │─── POST /auth/refresh ──▶│                       │                      │
  │  (old token "abc")        │                       │                      │
  │                  │        SHA-256("abc") = "a1b2" │                      │
  │                  │───── find_by_hash("a1b2") ───▶│                      │
  │                  │◀──── record (ROTATED!) ────────│                      │
  │                  │                                │                      │
  │                  │  ─── REUSE DETECTED ───        │                      │
  │                  │                                │                      │
  │                  │──── revoke_all_for_session ───▶│                      │
  │                  │◀─── n records revoked ─────────│                      │
  │                  │                                │                      │
  │                  │── find_by_id(session_id) ───────────────────────────▶│
  │                  │── session.revoke_due_to_token_reuse() ───────────────│
  │                  │     → pushes RefreshTokenReuseDetected               │
  │                  │     → pushes SessionRevokedDueToTokenReuse            │
  │                  │── save(session) ────────────────────────────────────▶│
  │                  │                                │                      │
  │◀── 401 Unauthorized ─────│                        │                      │
  │  (refresh_token_reuse)    │                        │                      │
```

---

## Consequences

### Positive

- Every stolen token attempt is detectable and causes automatic session revocation.
- The database never stores plaintext tokens.
- The ROTATED state makes the audit trail clear: when was each token rotated, by whom.
- `asyncio.Lock` is sufficient for the in-memory dev/test implementation.
- The `RefreshTokenRepository.rotate()` contract is explicitly defined, making
  PostgreSQL implementation straightforward.

### Negative / Trade-offs

- Stale token requests (client retry after first rotation succeeded) fail with
  `RefreshTokenReuseError` and trigger session revocation. This is a false positive.
  Mitigation: clients must not retry refresh requests; they must use the new token.

- Two-phase update (token swap then session pointer update) creates a small window
  where the session's `refresh_token_id` is stale. In production, both must be in
  the same DB transaction.

- One database lookup per `/auth/refresh` request (vs. zero for a pure JWT approach).
  This is acceptable — refresh requests are infrequent (every 15 minutes per device).

### Neutral

- The `InMemoryRefreshTokenStore` loses all state on server restart. This is expected
  for a dev/test implementation. Users must re-authenticate after restart in local dev.

---

## Related Decisions

- **ADR-003**: HS256 JWT access tokens — refresh tokens replace these at expiry.
- **ADR-004**: Argon2id — used for password hashing, NOT for refresh token hashing
  (different entropy characteristics; see SHA-256 rationale above).

## Future Decisions Deferred

- PostgreSQL `RefreshTokenRepository` implementation (TASK-2.7+)
- Redis-backed `TokenRevocationService` for JTI blacklist (TASK-2.7+)
- Sliding refresh token expiry (renew `expires_at` on each rotation)
- HMAC-SHA256 with a rotating server-side key (optional additional hardening)
- Background cleanup job for EXPIRED token records older than 30 days
