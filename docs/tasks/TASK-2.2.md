# TASK-2.2 — Identity Context: Password Service Contracts

**Status:** Complete
**Phase:** 2 — Sprint 2
**Depends on:** TASK-2.1 (Identity Context — Authentication Domain)
**Blocks:** TASK-2.3 (Authentication Infrastructure — bcrypt, Argon2, Redis)

---

## Objective

Create future-proof contracts (Protocols, interfaces, and value object improvements)
for the password management subsystem. No cryptographic implementations, no hashing
libraries, no infrastructure code.

The guiding architectural constraint:

> The password hashing algorithm must be replaceable (bcrypt → Argon2id → passkeys)
> without ANY change to the domain model, application layer, or API layer.

---

## Scope

### In Scope

- `PasswordHasher` port interface (hash, verify, needs_rehash)
- `PasswordGenerator` port interface (generate)
- `PasswordStrengthPolicy` — supersedes `PasswordPolicy` from TASK-2.1
- `PasswordComplexityPolicy`, `PasswordHistoryPolicy`, `PasswordReusePolicy`,
  `PasswordExpiryPolicy`, `CredentialRotationPolicy`
- Application service contracts: `ChangePasswordService`, `ResetPasswordService`,
  `ValidatePasswordService`
- New domain errors: `PasswordReuseError`, `PasswordExpiredError`,
  `PasswordHashingError`, `PasswordGenerationError`
- New specifications: `ReusablePasswordSpecification`, `ExpiredPasswordSpecification`
- `PasswordHash` value object improvement (algorithm-agnostic)
- `AuthenticationCredential` improvement (add `password_changed_at`)

### Explicitly Out of Scope

- bcrypt, Argon2id, passlib, cryptography library
- JWT, Redis, FastAPI, SQLAlchemy
- Concrete implementations of any interface
- Database migrations
- Registration, login, session management

---

## Password Architecture

### Layered Contract Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│  API Layer (FastAPI)                                                 │
│  POST /auth/change-password, /auth/reset-password, /auth/validate  │
│  Depends on: ChangePasswordService, ResetPasswordService interfaces │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ depends on
┌─────────────────────▼───────────────────────────────────────────────┐
│  Application Layer                                                   │
│  application/interfaces.py                                          │
│  ChangePasswordService, ResetPasswordService, ValidatePasswordService│
│  Depends on: PasswordHasher, PasswordStrengthPolicy, domain entities│
└─────────────────────┬───────────────────────────────────────────────┘
                      │ depends on
┌─────────────────────▼───────────────────────────────────────────────┐
│  Domain Layer                                                        │
│  PasswordHasher, PasswordGenerator (ports)                          │
│  PasswordStrengthPolicy, PasswordComplexityPolicy, etc.             │
│  PasswordHash (value object)                                        │
│  AuthenticationCredential (aggregate — now has password_changed_at) │
│  ReusablePasswordSpecification, ExpiredPasswordSpecification        │
└─────────────────────┬───────────────────────────────────────────────┘
                      │ implemented by
┌─────────────────────▼───────────────────────────────────────────────┐
│  Infrastructure Layer (TASK-2.3)                                     │
│  BcryptPasswordHasher, Argon2PasswordHasher                         │
│  SecurePasswordGenerator                                            │
│  DefaultPasswordStrengthPolicy (reads from settings)                │
└─────────────────────────────────────────────────────────────────────┘
```

### Port-and-Adapter Pattern

`PasswordHasher` and `PasswordGenerator` are DRIVEN PORTS — they define what
the domain NEEDS from infrastructure. The concrete adapters (infrastructure)
implement them and are injected via FastAPI's dependency injection.

This guarantees:
- The domain knows nothing about bcrypt or Argon2.
- Switching algorithms requires only a new adapter class + config change.
- Tests inject a `MockPasswordHasher` — no real hashing in unit tests.

---

## Security Principles

### 1. Plaintext Never Persists in the Domain

The domain model (`AuthenticationCredential`) stores only `PasswordHash` (opaque
hash string). Plaintext passwords travel through the system only as far as
`PasswordHasher.hash()` — then they are discarded.

### 2. Constant-Time Verification

`PasswordHasher.verify()` MUST use constant-time comparison (bcrypt.checkpw,
Argon2.verify, or equivalent). This is documented in the interface contract.
The domain enforces this contractually — the test suite for infrastructure
adapters must verify timing properties.

### 3. PasswordHash Redaction

`PasswordHash.__repr__()` and `__str__()` always return `[REDACTED]`. The raw
hash can never appear in:
  - Log output (structlog, Python logging)
  - Exception messages
  - Pydantic validation errors
  - Sentry events
  - Test assertion output

### 4. Algorithm-Agnostic PasswordHash

Changed from bcrypt-specific regex to minimum-length check. Rationale: the
domain should not know which algorithm produced a hash. The algorithm is encoded
in the hash string itself (PHC format: `$argon2id$v=19$...`); the
`PasswordHasher.needs_rehash()` method detects when an upgrade is needed.

### 5. Maximum Password Length (DoS Prevention)

`PasswordStrengthPolicy.maximum_length` caps password length. bcrypt silently
truncates at 72 bytes; Argon2 does not truncate but is memory-hard. Without a
max-length guard, an attacker can submit multi-MB "passwords" to exhaust server
resources. The infrastructure adapter must enforce this BEFORE calling the
hashing library.

### 6. Password History Enforcement

`ReusablePasswordSpecification` checks candidate passwords against recent hashes
using `PasswordHasher.verify()` (not string comparison — bcrypt hashes are salted
and will never match by string equality). This correctly detects reuse.

---

## Password Lifecycle

```
User submits plaintext password
         │
         ▼
ValidatePasswordService.get_violations(password)
    ├─ PasswordStrengthPolicy.is_strong_enough()
    └─ PasswordComplexityPolicy checks
         │
         ▼ (if empty violations list)
ReusablePasswordSpecification.is_satisfied_by(password)
    └─ PasswordHasher.verify(password, each_recent_hash)
         │
         ▼ (if satisfied)
PasswordHasher.hash(password) → PasswordHash
         │
         ▼
AuthenticationCredential.change_password(new_hash)
    ├─ Sets password_hash
    ├─ Sets password_changed_at = now()
    ├─ Emits PasswordChanged event
    └─ Returns Result[None]
         │
         ▼
Application layer: revoke all other sessions
Application layer: notify user via email
Application layer: store old hash in history (PasswordHistoryRepository)
```

On next login after password change:
```
PasswordHasher.needs_rehash(stored_hash) → bool
    └─ If True: re-hash with current algorithm and save
         (transparent algorithm migration, no forced reset)
```

Password expiry check (after every successful login):
```
ExpiredPasswordSpecification.is_satisfied_by(credential)
    └─ elapsed > PasswordExpiryPolicy.max_password_age
         └─ If True: raise PasswordExpiredError → force password change flow
```

---

## Future Authentication Methods

The password subsystem was designed to coexist with, not block, future
authentication methods.

### Design Decisions That Enable Coexistence

| Decision | Rationale |
|---|---|
| `AuthenticationCredential` is password-specific | OAuth, passkeys, magic links get their own aggregate types |
| `PasswordHasher` is a named PORT | Future methods (WebAuthn, TOTP) get their own named ports |
| Application service interfaces are narrow | `ChangePasswordService` has no session awareness |
| Domain events are method-agnostic at the user level | `UserLoggedIn` fires regardless of auth method |

### Planned Credential Types

```
AuthenticationCredential    (password — this task)
OAuthCredential             (Google, GitHub, Apple — future)
PasskeyCredential           (WebAuthn — future)
MagicLinkCredential         (one-time email links — future)
TOTPCredential              (time-based OTP — future)
```

Each credential type is a separate aggregate. A user may have MULTIPLE
credential aggregates (password AND Google OAuth AND a passkey). The
application layer's `CredentialRouter` selects which aggregate to use
based on the login method the user chose.

This design is deliberately NOT implemented yet — only documented here
so that TASK-2.1/2.2 code does not inadvertently block it.

---

## Deliverables

### New Files

| File | Contents |
|---|---|
| `domain/services/password_hasher.py` | `PasswordHasher` Protocol (hash, verify, needs_rehash) |
| `domain/services/password_generator.py` | `PasswordGenerator` Protocol (generate) |
| `domain/services/password_policies.py` | `PasswordStrengthPolicy`, `PasswordComplexityPolicy`, `PasswordHistoryPolicy`, `PasswordReusePolicy`, `PasswordExpiryPolicy`, `CredentialRotationPolicy` |
| `application/__init__.py` | Application layer package |
| `application/interfaces.py` | `ChangePasswordService`, `ResetPasswordService`, `ValidatePasswordService` |

### Modified Files

| File | Change |
|---|---|
| `domain/value_objects/password_hash.py` | Algorithm-agnostic: removed bcrypt regex, added minimum-length guard; updated docstring |
| `domain/services/policies.py` | Removed `PasswordPolicy` (superseded by `PasswordStrengthPolicy`); kept `SessionPolicy`, `AuthenticationPolicy` |
| `domain/entities/credential.py` | Added `password_changed_at: datetime | None = None`; `create()` sets it to now; `change_password()` updates it |
| `domain/errors.py` | Added `PasswordReuseError`, `PasswordExpiredError`, `PasswordHashingError`, `PasswordGenerationError` |
| `domain/specifications/specifications.py` | Updated `StrongPasswordSpecification` to use `PasswordStrengthPolicy`; added `ReusablePasswordSpecification`, `ExpiredPasswordSpecification` |

---

## Definition of Done

- [x] `PasswordHasher` Protocol with hash / verify / needs_rehash
- [x] `PasswordGenerator` Protocol with generate
- [x] `PasswordStrengthPolicy` supersedes old `PasswordPolicy`
- [x] `PasswordComplexityPolicy` with character-class requirements
- [x] `PasswordHistoryPolicy` with max_history_count and retention period
- [x] `PasswordReusePolicy` with minimum age before reuse
- [x] `PasswordExpiryPolicy` with max age and warning period
- [x] `CredentialRotationPolicy` with forced-rotation conditions
- [x] `ChangePasswordService`, `ResetPasswordService`, `ValidatePasswordService` contracts
- [x] `PasswordHash` algorithm-agnostic (bcrypt regex → length guard)
- [x] `AuthenticationCredential.password_changed_at` field added
- [x] `PasswordReuseError`, `PasswordExpiredError`, `PasswordHashingError`, `PasswordGenerationError` added
- [x] `ReusablePasswordSpecification` uses `PasswordHasher.verify()` — no bcrypt import
- [x] `ExpiredPasswordSpecification` uses `PasswordExpiryPolicy.max_password_age`
- [x] Zero framework imports in domain and application contract files
- [x] Zero cryptographic library imports
- [x] All type hints present
- [x] Future authentication methods documented and not blocked
