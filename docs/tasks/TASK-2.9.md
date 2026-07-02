# TASK-2.9 — Identity Context: Login Application Service

**Sprint:** 2 — Identity Context
**Status:** ✅ Complete
**Depends on:** TASK-2.7 (RegistrationService), TASK-2.6 (RefreshTokenService)
**Implemented by:** Claude (Sonnet 4.6)

---

## Objective

Implement the **application-layer login service** for password-based authentication.
This completes the application tier for the authentication vertical slice. No FastAPI,
no SQLAlchemy, no HTTP exceptions — pure application orchestration over domain objects.

---

## Scope

**In scope (this task):**
- `domain/errors.py` — `AccountLockedError`, `EmailNotVerifiedError` (new errors)
- `domain/events/authentication_events.py` — `LoginAttemptFailed`, `PasswordRehashed` (new events)
- `application/commands.py` — `LoginUserCommand` (new command)
- `application/dtos.py` — `AuthenticatedSessionSummary`, `LoginResult` (new DTOs)
- `application/interfaces.py` — `RiskAction`, `RiskDecision`, `RiskAssessmentService`, `LoginService` Protocol
- `application/login_service.py` — `LoginConfiguration`, `LoginService` (full implementation)
- `application/login_handler.py` — `LoginUserHandler` (thin CQRS facade)
- `tests/unit/identity/authentication/test_login_service.py` — comprehensive tests

**Out of scope (deferred):**
- Login HTTP presentation layer (`POST /api/v1/auth/login`)
- Redis-backed `TokenRevocationService` (JTI blacklist)
- PostgreSQL-backed `SessionRepository`
- Concrete `RiskAssessmentService` implementation
- Step-up authentication / MFA for `RiskAction.CHALLENGE`

---

## Architecture

### Login Orchestration Flow

```
LoginUserCommand
  │
  ├─ Step 1: Parse email format (pure — Email VO)
  │   └─ Failure(InvalidEmailError) if malformed
  │
  ├─ Step 2: Load credential by email (read, outside UoW)
  │   └─ Storage failure → Failure(InfrastructureError)
  │
  ├─ Step 3: Constant-time guard — email not found
  │   └─ _equalize_timing(password) → Failure(InvalidCredentialsError)
  │      [LoginAttemptFailed published — user_id=None]
  │
  ├─ Step 4: Account state checks (pure — no I/O)
  │   ├─ is_active=False    → Failure(AccountDisabledError)   [+ event]
  │   ├─ is_locked=True     → Failure(AccountLockedError)     [+ event]
  │   └─ !is_email_verified → Failure(EmailNotVerifiedError)  [+ event]
  │      (if AuthenticationPolicy.require_email_verification)
  │
  ├─ Step 5: Risk assessment (optional insertion point)
  │   └─ risk.action=BLOCK → Failure(AuthenticationFailedError) [+ event]
  │      risk.action=CHALLENGE → ALLOW for now (step-up deferred)
  │      risk_service=None → proceed as ALLOW (default)
  │      risk service raises → fail open (ALLOW, log error)
  │
  ├─ Step 6: Verify password (CPU-bound, asyncio.to_thread)
  │   ├─ PasswordHashingError → Failure(PasswordHashingError)
  │   └─ is_valid=False → _record_failed_attempt (mini-UoW)
  │                      → Failure(InvalidCredentialsError) [+ event]
  │
  └─ Steps 7–10: Main Unit of Work (success path only)
      ├─ credential.record_successful_login()
      ├─ if needs_rehash → hash new password, set directly, emit PasswordRehashed
      ├─ await auth_repo.save(credential)
      ├─ RefreshTokenService.issue() → (plain_token, refresh_token_id)
      ├─ AuthenticationSession.create() → emits UserLoggedIn
      ├─ await session_repo.save(session)
      ├─ JWTService.create_access_token(AccessTokenClaims)
      └─ await uow.commit()
         └─ EventPublisher.publish([credential.pop_events(), service_events, session.pop_events()])
            └─ Success(AuthenticatedSessionSummary)
```

### Login Sequence Diagram

```
Client           Router          LoginService         UoW           EventPublisher
  │                │                   │               │                  │
  │  POST /login   │                   │               │                  │
  │───────────────►│                   │               │                  │
  │                │  execute(cmd)     │               │                  │
  │                │──────────────────►│               │                  │
  │                │                   │  find_by_email│                  │
  │                │                   │──────────────►│                  │
  │                │                   │  credential   │                  │
  │                │                   │◄──────────────│                  │
  │                │                   │ verify(pw,hash)                  │
  │                │                   │ [asyncio.to_thread]              │
  │                │                   │               │                  │
  │                │                   │  async with uow                  │
  │                │                   │  record_successful_login         │
  │                │                   │  RefreshTokenService.issue()     │
  │                │                   │  AuthenticationSession.create()  │
  │                │                   │  JWTService.create_access_token  │
  │                │                   │  commit()     │                  │
  │                │                   │──────────────►│                  │
  │                │                   │               │  publish(events) │
  │                │                   │               │─────────────────►│
  │                │  Success(summary) │               │                  │
  │                │◄──────────────────│               │                  │
  │  200 {tokens}  │                   │               │                  │
  │◄───────────────│                   │               │                  │
```

### Failed Login Sequence Diagram

```
Client           Router          LoginService       mini-UoW    EventPublisher
  │                │                   │               │               │
  │  POST /login   │                   │               │               │
  │───────────────►│                   │               │               │
  │                │  execute(cmd)     │               │               │
  │                │──────────────────►│               │               │
  │                │                   │  find_by_email │               │
  │                │                   │  verify → False               │
  │                │                   │               │               │
  │                │                   │  async with mini-uow          │
  │                │                   │  record_failed_login           │
  │                │                   │  save(credential)  │          │
  │                │                   │  commit()     │               │
  │                │                   │               │               │
  │                │                   │  publish([LoginAttemptFailed]) │
  │                │                   │───────────────────────────────►
  │                │  Failure(Invalid) │               │               │
  │                │◄──────────────────│               │               │
  │  401           │                   │               │               │
  │◄───────────────│                   │               │               │
```

---

## Domain Scenario Matrix

| # | Scenario | Input condition | Expected outcome | Domain events |
|---|----------|-----------------|------------------|---------------|
| 1 | Valid credentials, active account | Email found, pass matches, active, verified | `Success(AuthenticatedSessionSummary)` | `UserLoggedIn` |
| 2 | Email not found | Email absent in auth repo | `Failure(InvalidCredentialsError)` | `LoginAttemptFailed(user_id=None)` |
| 3 | Wrong password | Email found, verify=False | `Failure(InvalidCredentialsError)`, `failed_login_count++` | `LoginAttemptFailed` |
| 4 | Account disabled | `is_active=False` | `Failure(AccountDisabledError)` | `LoginAttemptFailed(reason=account_disabled)` |
| 5 | Account locked | `is_locked=True` | `Failure(AccountLockedError)` with `locked_until` | `LoginAttemptFailed(reason=account_locked)` |
| 6 | Email not verified | `is_email_verified=False` + policy requires | `Failure(EmailNotVerifiedError)` | `LoginAttemptFailed(reason=email_not_verified)` |
| 7 | Transparent password rehash | verify=True, `needs_rehash()=True` | Success, new hash stored, `PasswordRehashed` emitted | `UserLoggedIn`, `PasswordRehashed` |
| 8 | Risk assessment blocks | `RiskAssessmentService.assess()` returns `BLOCK` | `Failure(AuthenticationFailedError)` | `LoginAttemptFailed(reason=risk_blocked)` |
| 9 | Refresh token issuance | `RefreshTokenService.issue()` returns Success | Token in `AuthenticatedSessionSummary.plain_refresh_token` | (see #1) |
| 10 | Session created | `AuthenticationSession.create()` succeeds | Session in summary, `UserLoggedIn` emitted | `UserLoggedIn` |
| 11 | Persistence failure | `auth_repo.save()` or `session_repo.save()` raises | `Failure(InfrastructureError)`, UoW rolled back | none (commit never reached) |

---

## Design Decisions

### DD-1: Two distinct transaction scopes

**Decision:** Failed login recording uses an isolated mini-UoW, separate from the main
success-path UoW.

**Rationale:** The main UoW must be reserved for the success path (record_successful_login,
rehash, session, tokens). If we shared one UoW and password verification failed, the UoW
would already be open, and closing it before re-entering would violate the context manager
contract. The mini-UoW uses the same `UnitOfWork` instance — each `async with` opens a fresh
transaction scope.

**Consequence:** Failed login recording is best-effort. A DB failure during `record_failed_login`
is logged but does not change the HTTP response — the caller still receives `InvalidCredentialsError`.
This is the correct trade-off: brute-force protection depends on the DB being available, but a
transient storage failure should not cause a 503 response to a login attempt.

### DD-2: Constant-time response for unknown email

**Decision:** When email is not found, run a full Argon2 verification against a cached
dummy hash before returning `InvalidCredentialsError`.

**Rationale:** Without this, an attacker can enumerate valid email addresses by measuring
response latency. Argon2id at typical parameters takes 100–300ms. A fast response (no hash
to verify) leaks "this email is not registered."

**Implementation:** The dummy hash is computed once on the first "email not found" attempt
(lazy initialization). Subsequent attempts reuse the cached hash. This means the first such
attempt slightly exceeds typical latency (hash + verify instead of just verify), but this is
acceptable — the alternative of pre-computing the hash at startup requires an async context.

### DD-3: Transparent password rehash — direct field mutation

**Decision:** When `needs_rehash()` returns True, the new hash is written directly to
`credential.password_hash` and `credential.touch()` is called. `change_password()` is
intentionally NOT used.

**Rationale:**
- `change_password()` updates `password_changed_at` — wrong for rehash. The expiry clock
  should measure elapsed time since the user chose this password, not since the algorithm
  was upgraded.
- `change_password()` emits `PasswordChanged` — wrong for rehash. That event triggers
  "your password was changed" security notifications, which are alarming and incorrect.
- Direct mutation is safe: `AuthenticationCredential` is not frozen; field access is
  intentional here, documented in the service.

### DD-4: RiskAssessmentService — fail open

**Decision:** If `RiskAssessmentService.assess()` raises, login proceeds as ALLOW (fail open).

**Rationale:** The alternative (fail closed — block login on risk service failure) would
create a hard dependency on an external service that may not exist in all environments. In
MVP, no concrete implementation exists. Fail open means risk service outages don't lock all
users out. High-value accounts (admin users) may have additional protection via other controls.

### DD-5: RiskAction.CHALLENGE treated as ALLOW for now

**Decision:** `RiskAction.CHALLENGE` proceeds as `ALLOW` in the current implementation.

**Rationale:** Step-up authentication (MFA, OTP) is deferred to TASK-2.x. The challenge
infrastructure (OTP generation, MFA enrollment) does not yet exist. This decision is explicit:
the code has a comment and the LoginService is designed so that inserting the challenge flow
later only requires modifying the `if risk.action == RiskAction.CHALLENGE:` block.

### DD-6: Domain-level events vs. service-level events

**Pattern (same as RegistrationService):**
- `UserLoggedIn` — emitted by `AuthenticationSession.create()` (aggregate event, `session.pop_events()`)
- `PasswordRehashed` — emitted by the service directly (service-level integration event, `service_events` list)
- `LoginAttemptFailed` — emitted by `_publish_failed_attempt()` separately (best-effort, before return)

**Rationale:** `PasswordRehashed` is a transparent infrastructure operation that the domain
entity does not know about (hence direct field mutation, not `change_password()`). Publishing
it as a service event is consistent with the `EmailVerificationRequested` pattern in
`RegistrationService`.

---

## New Domain Additions

### Errors (`domain/errors.py`)

```python
class AccountLockedError(ForbiddenError):
    code = "account_locked"
    # Carries: locked_until: datetime | None
    # HTTP mapping: 403 (presentation layer may return 423 Locked)

class EmailNotVerifiedError(ForbiddenError):
    code = "email_not_verified"
    # HTTP mapping: 403
```

### Events (`domain/events/authentication_events.py`)

```python
@dataclass(frozen=True, kw_only=True)
class LoginAttemptFailed(DomainEvent):
    failure_reason: str  # "invalid_credentials" | "account_disabled" | ...
    ip_address: str | None
    user_id: str | None      # None for unknown email (prevents enumeration)
    user_agent: str | None

@dataclass(frozen=True, kw_only=True)
class PasswordRehashed(DomainEvent):
    user_id: str  # Transparent algorithm upgrade, NOT a user-visible password change
```

### Interfaces (`application/interfaces.py`)

```python
class RiskAction(Enum):     # ALLOW | CHALLENGE | BLOCK
class RiskDecision:         # action, reason, risk_score
class RiskAssessmentService(Protocol):  # assess(...) -> RiskDecision
class LoginService(Protocol):           # execute(LoginUserCommand) -> LoginResult
```

---

## Threat Model

### T1: Credential Stuffing

**Threat:** Attacker uses breached email/password pairs in bulk against the login endpoint.

**Mitigations (application layer, this task):**
- `record_failed_login` increments counter after each failure and applies lockout after
  `max_failed_attempts` (default 5) within `lockout_duration` (default 15 minutes).
- `LoginAttemptFailed` events enable downstream rate limiting and alerting.
- `RiskAssessmentService` insertion point allows IP-reputation and volume-based blocking.

**Mitigations (deferred):**
- Redis-backed sliding window rate limiter (TASK-2.x).
- Concrete `RiskAssessmentService` with IP reputation data.

### T2: Brute Force Against Known Account

**Threat:** Attacker iterates password combinations against a specific email.

**Mitigations:**
- Same as T1: lockout after 5 failures, 15-minute cooldown.
- Argon2id with default parameters makes each attempt ~100ms on modern hardware.
  With lockout after 5 attempts, an attacker must wait 15 minutes per 5 guesses.

### T3: Timing-Based Email Enumeration

**Threat:** Attacker measures response time differences between "email not found" (fast)
and "wrong password" (slow, dominated by Argon2) to enumerate valid accounts.

**Mitigation:**
- `_equalize_timing()` runs a full Argon2 verify against a cached dummy hash when email
  is not found. Response time is now dominated by Argon2 in both paths.
- Same `InvalidCredentialsError` is returned for both cases (no semantic difference).

### T4: Password Exfiltration via Logs

**Threat:** Plaintext password leaks into structured logs or exception traces.

**Mitigations:**
- `LoginUserCommand.password` uses `repr=False` and `__repr__` returns `[REDACTED]`.
- Service logs only: `email_domain`, `user_id`, `session_id`, error codes, boolean flags.
- `PlainRefreshToken.__repr__` and `__str__` return `[REDACTED]`.
- `AuthenticatedSessionSummary.__repr__` returns `[REDACTED]` for token fields.
- **Never logged:** password, password_hash, access_token, refresh_token.

### T5: Replay Attack on Login Response

**Threat:** Attacker captures a login response (tokens) and replays to impersonate the user.

**Mitigations (application layer):**
- JWT access tokens are short-lived (15 minutes) with `jti` claim for revocation.
- Refresh tokens are 256-bit opaque; stored as SHA-256 hash only.
- Session binding: `sid` claim in JWT ties it to the session.

**Mitigations (deferred):**
- Redis JTI blacklist for immediate token revocation on logout.
- Refresh token rotation on every `/auth/refresh` call (already implemented — TASK-2.6).

### T6: Timing Attack on Hash Algorithm Migration

**Threat:** An in-progress migration from bcrypt to Argon2id exposes timing differences.
Old hashes (bcrypt, fast verify) respond faster than new hashes (Argon2id, slow verify).

**Mitigation:**
- `needs_rehash()` detects old-format hashes immediately after successful verification.
- The rehash is transparent — the stored algorithm migrates silently without user action.
- After migration, both paths use Argon2id with consistent timing.

### T7: Session Fixation

**Threat:** Attacker establishes a session token before authentication and tricks the
victim into using it, gaining control after the victim authenticates.

**Mitigation:**
- A new `session_id` is generated for every login (`SessionId(self._uuid.generate())`).
- Sessions are never reused across login events.
- No session identifiers are exposed before successful authentication.

### T8: Account Enumeration via Error Code Differentiation

**Threat:** Different error codes for "account disabled" vs. "wrong password" vs. "locked"
could reveal account state even for unknown email addresses.

**Current state:**
- "Email not found" returns `InvalidCredentialsError` (same as "wrong password").
- "Account disabled", "Account locked", "Email not verified" return distinct errors for
  KNOWN accounts only. This is intentional — a 403 response confirms the account exists.

**Accepted risk:** Revealing account existence (but not credential validity) for accounts
that are disabled or locked is accepted. The alternative (returning 401 for everything)
would make security-related error handling in the client impossible. This is a standard
industry trade-off (see: GitHub, Stripe error handling patterns).

---

## Self-Review (Principal Application Architect)

### 1. Improvements Over Initial Design

- `_equalize_timing()` is lazily initialized rather than requiring a pre-computed dummy
  hash in `LoginConfiguration`. This avoids DI complexity and async-at-startup complications.
- `_record_failed_attempt()` is best-effort with explicit logging rather than silently
  swallowing errors. Operations teams can diagnose if failed attempts aren't being persisted.
- `RiskAssessmentService` is fail-open with explicit error logging — risk service unavailability
  doesn't block production logins.
- `PasswordRehashed` event is published AFTER the main UoW commit, following the same
  "events after commit" invariant as `UserLoggedIn`.

### 2. Architectural Decisions

- **Two-transaction design** (DD-1): separates failed-attempt tracking from session creation.
- **Direct field mutation for rehash** (DD-3): correct choice; `change_password()` has
  wrong side effects for a transparent algorithm migration.
- **Fail open for risk service** (DD-4): correct for MVP; can tighten per account tier later.
- **`LoginAttemptFailed` published outside UoW**: this event doesn't need transaction
  protection — it's an audit event that should fire even on storage failures.

### 3. Login Orchestration Flow

The flow implements the canonical authenticate-then-authorize pattern:
1. Verify identity (email + password)
2. Check authorization state (active, not locked, email verified)
3. Apply risk controls (optional)
4. Issue session artefacts (session, refresh token, JWT)

The atomicity guarantee: steps 7–10 are a single UoW. Either all succeed (commit) or
none persist (rollback). The user cannot receive tokens without a committed session record.

### 4. Threat Model Summary

Eight threats addressed across T1–T8. The highest residual risks are:
- **T1/T2 (brute force/stuffing):** lockout is in place but rate limiting is still
  missing from the presentation layer (TASK-2.x).
- **T5 (replay):** mitigated by short JWT TTL; Redis JTI blacklist (full revocation)
  is still deferred.
- **T8 (enumeration via error code):** accepted per industry practice.

### 5. Performance Considerations

- `asyncio.to_thread()` is used for two CPU-bound operations: `verify()` and optionally
  `hash()` (for rehash). Both use the thread pool to avoid blocking the event loop.
- Credential lookup (`find_by_email`) is a single indexed read — fast in both InMemory
  and PostgreSQL (email column has UNIQUE index).
- JWT signing (PyJWT) is synchronous but fast enough (<1ms) to run in the event loop.
- The dummy hash for timing equalization is computed once and cached. First unknown-email
  attempt pays the full cost (~100–300ms) to compute the cache; subsequent attempts only
  pay verify cost (~100–300ms), which is correct.

### 6. Remaining TODOs

| Priority | Item |
|---|---|
| High | TASK-2.x: Login presentation layer (`POST /api/v1/auth/login`) |
| High | TASK-2.x: Redis-backed rate limiter for login (5 req/min/IP, 10/hr/account) |
| High | TASK-2.x: Redis JTI blacklist (`TokenRevocationService`) |
| Medium | TASK-2.x: PostgreSQL-backed `SessionRepository` + Alembic migration |
| Medium | TASK-2.x: `POST /api/v1/auth/refresh` + refresh token rotation flow |
| Medium | TASK-2.x: Concrete `RiskAssessmentService` (IP reputation, geolocation anomaly) |
| Low | TASK-2.x: Step-up authentication for `RiskAction.CHALLENGE` (MFA, OTP) |
| Low | TASK-2.x: Adaptive lockout (progressive delays instead of flat lockout duration) |

### 7. Future Impact

**Login API (`POST /api/v1/auth/login`):**
- Uses same `RequestContext`, `DataEnvelope`, RFC 7807 error shape as registration.
- `AuthenticatedSessionSummary` maps directly to `LoginResponse` Pydantic schema.
- `plain_refresh_token.as_client_token()` is the only safe extraction path.
- `map_login_failure()` handles: 401 (InvalidCredentials), 403 (AccountDisabled/Locked/NotVerified),
  400 (InvalidEmail), 503 (PasswordHashingError), 500 (InfrastructureError).

**Auth Middleware (JWT validation):**
- Uses `AccessTokenClaims.sid` to identify the session.
- Uses `AccessTokenClaims.token_version` + `session_version` for force-logout without Redis.
- Will call `TokenRevocationService.is_revoked(jti=claims.jti)` for explicit logout support.

**OAuth / Passkeys:**
- `LoginUserHandler` is already structured for command-dispatch. Add `OAuthLoginHandler`
  and `PasskeyLoginHandler` as separate handlers, dispatched by a `LoginHandlerRouter`.
- `RiskAssessmentService` applies to all login methods — the interface is provider-agnostic.

**Email Verification (`POST /api/v1/auth/verify-email`):**
- After verification, `AuthenticationCredential.verify_email()` is called.
- If `AuthenticationPolicy.require_email_verification=True`, users must pass email
  verification before `LoginService` allows login (enforced at Step 4).

**Multi-device Sessions:**
- `LoginUserCommand.device_id` and `device_name` are already plumbed to `RefreshTokenService.issue()`.
- `AuthenticationPolicy.max_concurrent_sessions` (enforced via `SessionRepository.find_by_user_id()`)
  is not yet enforced in `LoginService` — deferred to the PostgreSQL session repository.

**Adaptive Authentication:**
- `RiskAssessmentService` is the primary hook. Phase 1: IP reputation. Phase 2: geolocation
  anomaly + impossible travel. Phase 3: full ML risk scoring.
- `RiskAction.CHALLENGE` activates MFA — the challenge flow returns a `session_challenge_token`
  to the client, which presents it along with the OTP for `/auth/challenge/verify`.

---

## Definition of Done

- [x] Implementation matches task specification
- [x] `AccountLockedError`, `EmailNotVerifiedError` added to `domain/errors.py`
- [x] `LoginAttemptFailed`, `PasswordRehashed` added to `domain/events/`
- [x] `LoginUserCommand` added to `application/commands.py` (password `repr=False`)
- [x] `AuthenticatedSessionSummary`, `LoginResult` added to `application/dtos.py`
- [x] `RiskAssessmentService`, `LoginService` Protocols added to `application/interfaces.py`
- [x] `LoginService` implements all 11 domain scenarios
- [x] `LoginUserHandler` created as thin CQRS facade
- [x] All functions have type hints
- [x] No FastAPI / SQLAlchemy / HTTP exceptions in application layer
- [x] Uses Result pattern — never raises for expected failures
- [x] Uses UnitOfWork — success path is atomic
- [x] Shared Kernel protocols reused (UnitOfWork, Clock, UUIDProvider, EventPublisher)
- [x] Domain layer entities unchanged (no new methods on credentials/sessions)
- [x] Password rehash supported (transparent, correct event, correct field semantics)
- [x] Future authentication providers supported (RiskAssessmentService insertion point)
- [x] Sensitive data never logged (password, hash, JWT, refresh token)
- [x] Constant-time guard for timing-based enumeration prevention
- [x] Unit tests written and passing (`test_login_service.py`)
- [x] Task specification (`TASK-2.9.md`) complete
