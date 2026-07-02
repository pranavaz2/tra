# TASK-2.1 — Identity Context: Authentication Domain

**Status:** Complete
**Phase:** 2 — Sprint 2
**Depends on:** TASK-003.2 (Shared Kernel Foundation), TASK-005 (Database Foundation)
**Blocks:** TASK-2.2 (Authentication Infrastructure + Use Cases), TASK-2.3 (Authentication API)

---

## Objective

Build the **pure domain model** for the Authentication bounded context within the
Identity Context. Zero infrastructure. Zero framework imports. Only domain concepts
expressed as Python classes.

This layer is the innermost ring of Clean Architecture — it has no dependencies
except the shared kernel (`app.shared.domain.*`).

---

## Scope

### In Scope

- Module package hierarchy (`identity/authentication/{domain,api,application,infrastructure,tests}/`)
- Domain errors (authentication-specific error classes)
- Value Objects: `UserId`, `SessionId`, `RefreshTokenId`, `Email`, `PasswordHash`
- Domain Events: `UserRegistered`, `UserLoggedIn`, `UserLoggedOut`, `SessionExpired`,
  `PasswordChanged`, `RefreshTokenRotated`
- Aggregate Roots: `AuthenticationCredential`, `AuthenticationSession`
- Repository Interfaces: `AuthenticationRepository`, `SessionRepository` (Protocols)
- Service Policy Interfaces: `PasswordPolicy`, `SessionPolicy`, `AuthenticationPolicy` (Protocols)
- Domain Specifications: `ValidEmailSpecification`, `StrongPasswordSpecification`,
  `ActiveSessionSpecification`
- README placeholders for non-domain layers
- This task specification document

### Explicitly Out of Scope

- Password hashing (bcrypt) — infrastructure concern
- JWT creation or verification — infrastructure concern
- Redis token revocation — infrastructure concern
- SQLAlchemy ORM models — infrastructure concern
- FastAPI routes or schemas — API concern
- Use cases or application services — application concern
- Alembic migrations — blocked on TASK-2.2
- Any external library import (no `passlib`, no `python-jose`, no `redis`)

---

## Domain Model

### Ubiquitous Language

| Term | Definition |
|---|---|
| **Authentication Credential** | The email + password-hash pair that identifies a user. One per user. |
| **Authentication Session** | An active login event. Created on login, destroyed on logout or expiry. |
| **Refresh Token Id** | An opaque UUID that maps to a session. Rotated on every `/auth/refresh`. |
| **Token Rotation** | Issuing a new refresh token and invalidating the previous one. |
| **Token Family** | All refresh tokens ever issued for a single session lifetime. |
| **Lockout** | A temporary suspension of login attempts after too many failures. |
| **Email Verification** | The process of confirming a user owns the email address they registered. |
| **Superseded Token** | A refresh token that has been replaced by rotation. Reuse = stolen token. |

### Aggregate Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│  AuthenticationCredential (AggregateRoot[UserId])               │
│                                                                  │
│  entity_id: UserId          ← identity across all contexts      │
│  email: Email               ← unique, normalised               │
│  password_hash: PasswordHash ← opaque, bcrypt format only      │
│  is_email_verified: bool                                        │
│  is_active: bool                                                │
│  failed_login_count: int    ← reset on successful login        │
│  locked_until: datetime?    ← cleared when count resets        │
│  last_login_at: datetime?                                       │
│                                                                  │
│  Events: UserRegistered, PasswordChanged                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  AuthenticationSession (AggregateRoot[SessionId])               │
│                                                                  │
│  entity_id: SessionId                                           │
│  user_id: UserId            ← FK into the credential aggregate │
│  refresh_token_id: RefreshTokenId ← current active token      │
│  expires_at: datetime       ← session TTL                      │
│  last_active_at: datetime   ← updated on each activity         │
│  revoked_at: datetime?      ← None = active; set = revoked    │
│  ip_address: str?           ← audit only                      │
│  user_agent: str?           ← audit only                      │
│                                                                  │
│  Events: UserLoggedIn, UserLoggedOut, SessionExpired,           │
│           RefreshTokenRotated                                    │
└─────────────────────────────────────────────────────────────────┘
```

The two aggregates are related by `UserId` — they do NOT reference each other
directly. Cross-aggregate references use only identity (value objects), never
object references.

### Value Object Invariants

| Value Object | Invariant | Error |
|---|---|---|
| `Email` | Matches practical email regex after strip + lowercase | `InvalidEmailError` |
| `PasswordHash` | Matches bcrypt sentinel pattern `$2[aby]$nn$...` (60 chars) | `ValueError` (programming error) |
| `UserId` | Any valid UUID v4 | `ValueError` |
| `SessionId` | Any valid UUID v4 | `ValueError` |
| `RefreshTokenId` | Any valid UUID v4 | `ValueError` |

`Email` normalises to lowercase on construction — `object.__setattr__` bypass is
intentional and documented in the implementation.

`PasswordHash.repr()` always returns `PasswordHash([REDACTED])` — the raw hash
can never appear in logs or exception messages.

### Domain Event Conventions

All events are frozen dataclasses. Id fields are stored as `str` (not `UUID`) to
enable serialisation without domain knowledge of UUID.

Subclasses use `@dataclass(frozen=True, kw_only=True)` to work around Python's
dataclass inheritance constraint — `DomainEvent` has default-valued fields after
a required field, so subclass fields must be keyword-only to avoid a `TypeError`.

### Result Pattern Usage

Methods that can fail in an expected, recoverable way return `Result[T]`:

| Method | Success | Failure |
|---|---|---|
| `AuthenticationCredential.change_password()` | `Success(None)` | `Failure(AccountDisabledError)` |
| `AuthenticationSession.rotate_refresh_token()` | `Success(previous_token_id)` | `Failure(SessionExpiredError)` or `Failure(SessionRevokedError)` |

Methods that cannot fail in a domain sense are `-> None` (e.g., `revoke()`,
`record_activity()`).

---

## Key Design Decisions

### Password Verification is Not in the Domain

`AuthenticationCredential` stores a `PasswordHash` but never compares plaintext
to hash. That is `bcrypt.checkpw()` — a CPU-intensive cryptographic operation that
belongs in the infrastructure layer's password adapter. The domain records the
outcome (success → `record_successful_login()`; failure → `record_failed_login()`).

### Token Rotation Returns the Previous Token

`rotate_refresh_token(new_token_id)` returns `Success(previous_token_id)`. The
application layer needs this to immediately revoke the previous token in Redis.
Without the return value, the caller would have to reload the session from the
database to find out what was rotated out.

### revoke() is Idempotent

`AuthenticationSession.revoke()` checks `is_revoked` before acting and returns
early if already revoked. Logout-all-devices iterates sessions and calls `revoke()`
on each — idempotence prevents duplicate `UserLoggedOut` events.

### Sessions Are Hard-Deleted, Not Soft-Deleted

The `SessionRepository` interface defines `delete()` as a hard delete.
Sessions are security infrastructure — keeping revoked sessions indefinitely
is a storage cost with no domain benefit. Revoked sessions are cleaned up by
a background job after a short retention window (audit log in infrastructure).

### Email Normalisation Happens in the Value Object

`Email.__post_init__` normalises before validation. This means the canonical form
is always lowercase + stripped, regardless of how the client sent it. Two `Email`
objects with the same normalised address are equal (frozen dataclass equality).

---

## Deliverables

### New Files

| File | Purpose |
|---|---|
| `app/modules/identity/__init__.py` | Identity context package |
| `app/modules/identity/authentication/__init__.py` | Authentication bounded context package |
| `app/modules/identity/authentication/domain/__init__.py` | Domain layer package |
| `app/modules/identity/authentication/domain/errors.py` | 10 authentication-specific error classes |
| `app/modules/identity/authentication/domain/value_objects/user_id.py` | `UserId` |
| `app/modules/identity/authentication/domain/value_objects/session_id.py` | `SessionId` |
| `app/modules/identity/authentication/domain/value_objects/refresh_token_id.py` | `RefreshTokenId` |
| `app/modules/identity/authentication/domain/value_objects/email.py` | `Email` + `is_valid_email_format()` |
| `app/modules/identity/authentication/domain/value_objects/password_hash.py` | `PasswordHash` |
| `app/modules/identity/authentication/domain/events/authentication_events.py` | 6 domain events |
| `app/modules/identity/authentication/domain/entities/credential.py` | `AuthenticationCredential` aggregate |
| `app/modules/identity/authentication/domain/entities/session.py` | `AuthenticationSession` aggregate |
| `app/modules/identity/authentication/domain/repositories/interfaces.py` | `AuthenticationRepository`, `SessionRepository` |
| `app/modules/identity/authentication/domain/services/policies.py` | `PasswordPolicy`, `SessionPolicy`, `AuthenticationPolicy` |
| `app/modules/identity/authentication/domain/specifications/specifications.py` | 3 domain specifications |
| `app/modules/identity/authentication/api/README.md` | Placeholder |
| `app/modules/identity/authentication/application/README.md` | Placeholder |
| `app/modules/identity/authentication/infrastructure/README.md` | Placeholder |
| `app/modules/identity/authentication/tests/README.md` | Placeholder |
| `docs/tasks/TASK-2.1.md` | This document |

---

## Future Integration Points

### TASK-2.2 — Infrastructure Layer

Implementations of:
- `AuthenticationRepository` via `SQLAlchemyAuthenticationRepository`
- `SessionRepository` via `SQLAlchemySessionRepository`
- `PasswordPolicy`, `SessionPolicy`, `AuthenticationPolicy` reading from Pydantic settings
- bcrypt adapter (wraps `passlib.context.CryptContext`)
- JWT access-token service
- Redis token revocation blacklist

### TASK-2.3 — API Layer

FastAPI router with endpoints for register, login, refresh, logout, and email verification.
All routes use application-layer use cases from TASK-2.2; no business logic in the router.

---

## Definition of Done

- [x] Module package hierarchy created
- [x] `domain/errors.py` — 10 error classes extending shared kernel base classes
- [x] Value objects — all 5 implemented with invariant enforcement
- [x] Domain events — all 6 implemented as frozen dataclasses with `kw_only=True`
- [x] `AuthenticationCredential` aggregate — all methods, properties, domain events
- [x] `AuthenticationSession` aggregate — all methods, properties, domain events
- [x] Repository interfaces — `AuthenticationRepository`, `SessionRepository` as `@runtime_checkable Protocol`
- [x] Policy interfaces — `PasswordPolicy`, `SessionPolicy`, `AuthenticationPolicy` as `@runtime_checkable Protocol`
- [x] Specifications — `ValidEmailSpecification`, `StrongPasswordSpecification`, `ActiveSessionSpecification`
- [x] README placeholders for api/, application/, infrastructure/, tests/
- [x] Zero framework imports in domain layer (no FastAPI, SQLAlchemy, Redis, passlib, jose)
- [x] All public functions and class attributes have type hints
- [x] No `print()`, no `os.environ`, no hardcoded secrets
- [x] Result pattern used for expected failures
- [x] `PasswordHash` never appears in repr or str output
- [x] `Email` normalises to lowercase on construction
