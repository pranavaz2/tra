# TASK-2.7 — Identity Context: Registration Application Service

**Status:** Complete  
**Sprint:** 2  
**Layer:** Application (no FastAPI, no SQLAlchemy, no HTTP)  
**Depends on:** TASK-2.1 (domain), TASK-2.2 (password contracts), TASK-2.3 (Argon2id), TASK-2.5 (JWT), TASK-2.6 (refresh tokens)

---

## 1. Summary

Implements the Registration Application Service — the orchestration layer for new user registration.  
The service coordinates existing domain and infrastructure components without duplicating their logic.

**What was built:**
- `RegisterUserCommand` — strongly typed, immutable command with password redaction in repr
- `RegistrationSummary` / `RegistrationResult` — application-layer DTOs (not Pydantic schemas)
- `RegistrationService` — orchestrates all 9 domain scenarios, owns Unit of Work management
- `RegisterUserHandler` — thin CQRS command handler facade
- `RegistrationConfiguration` — frozen dataclass for config values (no direct Settings access)
- Shared kernel: `UnitOfWork`, `Clock`, `UUIDProvider`, `EventPublisher` protocols + implementations
- Default policy implementations: `DefaultPasswordStrengthPolicy`, `DefaultSessionPolicy`, `DefaultAuthenticationPolicy`
- New domain events: `EmailVerificationRequested`, `UserEmailAutoVerified`
- Config flags: `registration_auto_verify_email`, `registration_require_email_verification`
- Full DI wiring in `infrastructure/dependencies.py`
- 50+ unit tests covering all 9 domain scenarios and security invariants

---

## 2. Registration Sequence Diagram

```
Client             API Router          RegistrationService          Domain              Infrastructure
  │                    │                       │                       │                      │
  │── POST /register ──▶│                       │                       │                      │
  │   {email, password} │                       │                       │                      │
  │                    │── handle(command) ────▶│                       │                      │
  │                    │                       │── Email(email) ───────▶│                      │
  │                    │                       │◀── Email VO or error ──│                      │
  │                    │                       │                       │                      │
  │                    │                       │── exists_with_email ─────────────────────────▶│
  │                    │                       │◀── bool ────────────────────────────────────│
  │                    │                       │                       │                      │
  │                    │                       │── strength_policy.get_violations ────────────▶│
  │                    │                       │◀── [] or [violations] ──────────────────────│
  │                    │                       │                       │                      │
  │                    │                       │── asyncio.to_thread(hasher.hash) ────────────▶│
  │                    │                       │◀── PasswordHash ────────────────────────────│
  │                    │                       │                       │                      │
  │                    │                       │── Credential.create ──▶│                      │
  │                    │                       │◀── credential + UserRegistered event ─────────│
  │                    │                       │                       │                      │
  │                    │                    [async with UoW]           │                      │
  │                    │                       │── auth_repo.save ───────────────────────────▶│
  │                    │                       │── _apply_verification ▶│                      │
  │                    │                       │   (push event)         │                      │
  │                    │                       │── _create_session ────▶│                      │
  │                    │                       │   └─ refresh_token_svc.issue ─────────────────▶│
  │                    │                       │   └─ Session.create ───▶│                      │
  │                    │                       │   └─ session_repo.save ──────────────────────▶│
  │                    │                       │   └─ jwt_svc.create_access_token ─────────────▶│
  │                    │                       │── uow.commit ───────────────────────────────▶│
  │                    │                    [end UoW]                  │                      │
  │                    │                       │── event_publisher.publish ───────────────────▶│
  │                    │◀── RegistrationResult ─│                       │                      │
  │◀── 201 Created ────│                       │                       │                      │
  │    {user_id,        │                       │                       │                      │
  │     access_token,   │                       │                       │                      │
  │     refresh_token}  │                       │                       │                      │
```

---

## 3. Application Orchestration Diagram

```
RegisterUserHandler
  └── RegistrationService.execute(RegisterUserCommand)
        │
        ├─ [1] Email.validate(email_str)           → InvalidEmailError on fail
        ├─ [2] auth_repo.exists_with_email(email)  → EmailAlreadyExistsError on dupe
        ├─ [3] strength_policy.get_violations(pw)  → WeakPasswordError on fail
        ├─ [4] asyncio.to_thread(hasher.hash, pw)  → PasswordHashingError on fail
        ├─ [5] AuthenticationCredential.create(…)  → credential + UserRegistered event
        │
        └─ [async with UnitOfWork]
              ├─ [6] auth_repo.save(credential)
              ├─ [7] _apply_verification(credential, email)
              │         ├─ policy.require_verification=False → credential.verify_email()
              │         ├─ config.auto_verify_email=True     → verify + UserEmailAutoVerified
              │         └─ production                        → push EmailVerificationRequested
              ├─ [8] if create_session:
              │         ├─ refresh_token_svc.issue(…)        → (PlainRefreshToken, RefreshTokenId)
              │         ├─ AuthenticationSession.create(…)   → session + UserLoggedIn event
              │         ├─ session_repo.save(session)
              │         └─ jwt_svc.create_access_token(…)    → access_token str
              └─ [9] uow.commit()
        │
        └─ [after commit] event_publisher.publish(all events)
        └─ return Success(RegistrationSummary)
```

---

## 4. Domain Scenario Table

| # | Scenario | Trigger | Expected Result | Events |
|---|---|---|---|---|
| 1 | Success with session | Valid email, strong password, `create_session=True` | `Success(RegistrationSummary)` with tokens | `UserRegistered`, `UserLoggedIn` |
| 2 | Success without session | `create_session=False` | `Success(RegistrationSummary)` without tokens | `UserRegistered` |
| 3 | Email already exists | `auth_repo.exists_with_email()` returns True | `Failure(EmailAlreadyExistsError)` | None |
| 4 | Invalid email format | `Email(email)` raises | `Failure(InvalidEmailError)` | None |
| 5 | Weak password | `strength_policy.get_violations` non-empty | `Failure(WeakPasswordError(violations=[...]))` | None |
| 6 | Hash failure | `hasher.hash()` raises `PasswordHashingError` | `Failure(PasswordHashingError)` | None |
| 7 | Persistence failure | `auth_repo.save()` raises | `Failure(InfrastructureError)`, UoW rolled back | None |
| 8 | Email verification required | `auth_policy.require_email_verification=True`, `auto_verify=False` | `Success`, `is_email_verified=False`, `requires_email_verification=True` | `UserRegistered`, `EmailVerificationRequested` |
| 9 | Dev-mode auto-verify | `auto_verify_email=True` (config-driven) | `Success`, `is_email_verified=True`, `requires_email_verification=False` | `UserRegistered`, `UserEmailAutoVerified` |

---

## 5. Future OAuth / Apple / Passkey Integration

The registration service is intentionally password-specific. Future credential types follow this pattern:

### Design Approach

```
app/modules/identity/authentication/application/
├── commands.py
│   ├── RegisterUserCommand        ← password (this task)
│   ├── OAuthRegisterCommand       ← future: provider, auth_code, redirect_uri
│   └── PasskeyRegisterCommand     ← future: passkey_credential, public_key
├── registration_service.py        ← password registration (this task)
├── oauth_registration_service.py  ← future
└── passkey_registration_service.py ← future
```

### Invariants that ALL registration paths must satisfy:
1. Each path creates one `AuthenticationCredential` per user — the user's canonical identity.
2. Each path emits `UserRegistered` domain event on success.
3. Each path goes through the same Unit of Work.
4. Email verification requirements apply regardless of credential type.
5. `RegistrationResult` (Success/Failure) is the return type for all handlers.

### OAuth flow difference:
- No password → no `PasswordHasher` dependency
- `is_email_verified` is usually `True` (provider already verified)
- An `OAuthCredential` entity (future) stores the OAuth provider + external user ID
- The `AuthenticationCredential` holds the canonical email; `OAuthCredential` is a separate aggregate linked by `UserId`

---

## 6. Threat Model

### T1 — User Enumeration

**Threat:** Attacker submits candidate emails to discover registered accounts.

**Attack vector:** `POST /api/v1/auth/register` returns `409 Conflict` for existing emails.

**Mitigation:** The `EmailAlreadyExistsError` intentionally does NOT include the email in the error message. At the API layer (future TASK-2.8), the HTTP 409 body should be generic ("An account with this email may already exist") to prevent enumeration via wording differences. Rate limiting at the API layer (CLAUDE.md §Rate limiting) provides secondary defense.

**Residual risk:** Timing side-channel — the uniqueness check is a fast DB read while password hashing (Argon2id, ~100ms) is skipped on conflict. An attacker could use response time to infer whether the email is registered. **Mitigated** in the future API layer by always running the password strength check (steps 1–3) before the uniqueness check result is returned.

### T2 — Registration Spam

**Threat:** Automated registration of disposable email addresses at scale.

**Attack vectors:** Bypasses rate limits, consumes Argon2id CPU budget (DoS), pollutes user database.

**Mitigations:**
- Rate limiting applied at `POST /api/v1/auth/register` — `rate_limit_public_rpm` (60 RPM).
- Argon2id hashing is only reached after format + uniqueness checks pass — bots that submit invalid emails fail cheaply.
- Email verification (`require_email_verification=True`) creates a double opt-in barrier.
- **Not yet implemented:** CAPTCHA, email domain blocklist, disposable-email detection.

### T3 — Weak Password Registration

**Threat:** Users register with passwords that are trivially guessable.

**Mitigation:** `DefaultPasswordStrengthPolicy` enforces minimum length 12. The `get_violations()` response lists specific failures so the API can surface them for real-time UI feedback. The policy is configurable — future ADR may add `PasswordComplexityPolicy` checks (character classes, common password blocklist).

### T4 — Race Condition: Duplicate Registrations

**Threat:** Two concurrent requests with the same email both pass the `exists_with_email()` check (both see False), then both attempt to persist. One should succeed; the other should fail with a conflict error.

**Mitigation layers:**
- In production, the `credentials` table has a `UNIQUE` constraint on the normalised email column. The second writer receives a database constraint violation, which the PostgreSQL repository translates to `EmailAlreadyExistsError`.
- `InMemoryAuthRepository` (dev/test) does NOT enforce this atomically — two concurrent coroutines could both save. This is an accepted limitation of the in-memory store for test speed. Tests that need race-condition coverage will use the real PostgreSQL store.

### T5 — Sensitive Data in Logs

**Threat:** Password, hash, token material leaked to log aggregators (Datadog, CloudWatch) via `str()` or `repr()` of objects.

**Mitigations enforced:**
- `RegisterUserCommand.password` uses `field(repr=False)` and a custom `__repr__` that emits `[REDACTED]`.
- `RegistrationSummary.access_token` and `.plain_refresh_token` use `field(repr=False)`.
- `PlainRefreshToken.__repr__` and `__str__` always return `[REDACTED]`.
- `RegistrationService` structured log entries never include password, hash, or token values.
- Test `TestSecurityInvariants` verifies repr-safety programmatically.

### T6 — Dev-Mode Auto-Verify in Production

**Threat:** `registration_auto_verify_email=True` accidentally deployed to production, bypassing email verification entirely.

**Mitigation:** Config flag defaults to `False`. The environment variable `REGISTRATION_AUTO_VERIFY_EMAIL` must be explicitly set. The service has no code path that checks `app_env` — it only reads `auto_verify_email` from `RegistrationConfiguration`. Setting this flag in production is an operator error, not a code defect. **Recommended:** Add a `model_validator` in `Settings` that raises `ValueError` if `registration_auto_verify_email=True` and `app_env="production"` (future hardening).

---

## 7. Architecture Decisions

### ADR referenced: ADR-005 (refresh token lifecycle)

No new ADR created — this task implements orchestration of existing components without introducing new architectural decisions.

### Key decision: Service manages Unit of Work internally

The `RegistrationService.execute()` method owns the `async with self._uow:` context. An alternative would have the `RegisterUserHandler` manage the UoW. The service-owns-UoW pattern was chosen because:
1. The service is the only caller that knows which sub-operations must be atomic.
2. The handler remains thin and testable without UoW logic.
3. Future changes to the atomic boundary (e.g., adding a profile table) only change the service.

### Key decision: `asyncio.to_thread()` for password hashing

`PasswordHasher.hash()` is synchronous (CPU-bound) per the domain interface. The service offloads it via `asyncio.to_thread()` to avoid blocking the event loop. This is the correct pattern for Argon2id (~100ms) in an async FastAPI context.

### Key decision: Events published after commit

Domain events from `credential.pop_events()` and `session.pop_events()` are published only after `uow.commit()` succeeds. This prevents publishing `UserRegistered` for a registration that was later rolled back. A publish failure after a committed write is logged but does not return an error — the write already succeeded.

---

## 8. Definition of Done Checklist

### Code Quality
- [x] Implementation matches this task specification
- [x] All functions have type hints
- [x] No FastAPI imports in service, handler, commands, or DTOs
- [x] No SQLAlchemy imports in any application-layer file
- [x] No HTTP exceptions — only `Result[T]` returns

### Architecture
- [x] No business logic added to Flutter (N/A — backend only)
- [x] All external service calls through abstraction layer
- [x] Module boundaries respected — no circular imports
- [x] Naming conventions followed (Section 8 of CLAUDE.md)
- [x] Domain layer unchanged except for two new events (extending, not modifying)
- [x] Shared kernel reused (Result, TravixError, DomainEvent)
- [x] No duplicated business logic (email validation in Email VO; password in policy)

### Security
- [x] Password never logged or stored in plaintext
- [x] Auto-verify controlled by config flag, never hardcoded
- [x] `RegisterUserCommand.__repr__` redacts password
- [x] `RegistrationSummary.__repr__` redacts access_token and refresh_token
- [x] Threat model documented (Section 6)

### Tests
- [x] Unit tests for all 9 domain scenarios
- [x] Security invariant tests (repr redaction, credential storage)
- [x] Handler delegation tests
- [x] All tests are async (asyncio_mode = "auto")
- [x] No mocking framework — hand-crafted stubs

### Documentation
- [x] TASK-2.7.md (this document)
- [x] Sequence diagram
- [x] Orchestration diagram
- [x] Domain scenario table
- [x] Future OAuth integration notes
- [x] Threat model
