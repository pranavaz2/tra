# TASK-2.3 — Identity Context: Password Hashing Infrastructure

**Status:** Complete
**Phase:** 2 — Sprint 2
**Depends on:** TASK-2.2 (Password Service Contracts)
**Blocks:** TASK-2.4 (Registration), TASK-2.5 (Login)

---

## Objective

Implement the `PasswordHasher` infrastructure adapter using Argon2id.
The domain contracts created in TASK-2.2 are complete — this task wires
a production-grade implementation to them, registers it with FastAPI's
dependency injection, and ships a comprehensive test suite.

Architectural constraint:
> The infrastructure adapter must implement the domain Protocol exactly.
> No domain code was modified by this task.

---

## Scope

### In Scope

- `Argon2PasswordHasher` — concrete implementation of `PasswordHasher` Protocol.
- `Argon2Settings` — typed parameter container built from `app.config.Settings`.
- `get_password_hasher()` FastAPI dependency factory.
- `CurrentPasswordHasher` — injectable type alias.
- `CompromisedPasswordChecker` and `PasswordEntropyEvaluator` — documented
  placeholder Protocols (no concrete implementation yet).
- Configuration: five new `argon2_*` fields in `app.config.Settings`.
- Dependency: `argon2-cffi>=23.1.0,<25.0.0` added to `pyproject.toml`.
- Tests: 40+ unit test cases covering all contracts and edge cases.
- ADR-004: documents the Argon2id algorithm decision.

### Explicitly Out of Scope

- Registration, login, password change flows (those inject the hasher — future tasks).
- `MigratingPasswordHasher` composite adapter (future task, needed for bcrypt migration).
- `CompromisedPasswordChecker` concrete implementation (documented for future task).
- `PasswordEntropyEvaluator` concrete implementation (documented for future task).
- Integration tests (the hasher has no database or network dependency — unit tests
  with the real library are sufficient).
- Alembic migrations (no schema changes in this task).

---

## Architecture

### Dependency Direction

```
FastAPI route handler
    └─ CurrentPasswordHasher (type alias)
           └─ Depends(get_password_hasher)
                  └─ Argon2PasswordHasher  ← THIS TASK
                         └─ PasswordHasher Protocol (domain port, TASK-2.2)
```

The route handler declares `hasher: CurrentPasswordHasher`. FastAPI resolves
it to an `Argon2PasswordHasher` instance. The handler's type annotation is
`PasswordHasher` — not `Argon2PasswordHasher` — so the concrete type is
invisible to the application layer.

### Algorithm Migration Path

```
next login after settings change:
    1. Verify password → True
    2. hasher.needs_rehash(stored_hash) → True (params upgraded or non-Argon2)
    3. new_hash = hasher.hash(plain_password)
    4. credential.change_password(new_hash)
    5. repository.save(credential)

No user action required. No forced password reset.
```

### Singleton Lifecycle

`Argon2PasswordHasher` is constructed once via `_build_default_hasher()` (lru_cache).
The argon2-cffi `PasswordHasher` is stateless between calls — allocations happen
inside the C extension per hash operation. The singleton is safe to share across
all concurrent requests.

---

## Deliverables

### New Files

| File | Contents |
|---|---|
| `app/modules/identity/authentication/infrastructure/__init__.py` | Package marker |
| `app/modules/identity/authentication/infrastructure/password_hasher.py` | `Argon2Settings`, `Argon2PasswordHasher`, `_build_default_hasher` |
| `app/modules/identity/authentication/infrastructure/dependencies.py` | `get_password_hasher`, `CurrentPasswordHasher` |
| `app/modules/identity/authentication/domain/services/password_security.py` | `CompromisedPasswordChecker`, `PasswordEntropyEvaluator` (placeholders) |
| `tests/unit/identity/__init__.py` | Test package marker |
| `tests/unit/identity/authentication/__init__.py` | Test package marker |
| `tests/unit/identity/authentication/test_argon2_password_hasher.py` | Full test suite |
| `docs/adr/ADR-004-argon2id-password-hashing.md` | Algorithm decision record |

### Modified Files

| File | Change |
|---|---|
| `pyproject.toml` | Added `argon2-cffi>=23.1.0,<25.0.0` to dependencies |
| `app/config.py` | Added `argon2_time_cost`, `argon2_memory_cost`, `argon2_parallelism`, `argon2_hash_len`, `argon2_salt_len` to `Settings` |

---

## Security Properties

### What this task guarantees

1. **Random salt per hash** — argon2-cffi generates a cryptographic random salt
   via `os.urandom()` on every `hash()` call. Two hashes of the same password
   are always different.

2. **Constant-time verification** — `Argon2PasswordHasher.verify()` returns False
   (never raises) on mismatch. The C reference implementation uses constant-time
   memory comparison. The Python exception is caught before it reaches callers.

3. **No plaintext exposure** — the plaintext password is passed directly to the
   C extension and never stored, logged, or included in exception messages.
   `PasswordHash.__repr__()` returns `[REDACTED]`.

4. **Algorithm self-description** — the PHC string format encodes all parameters
   inside the hash string itself (e.g., `$argon2id$v=19$m=65536,t=3,p=4$…`).
   No out-of-band parameter storage is required.

5. **Upgrade detection** — `needs_rehash()` returns True when stored parameters
   are below the current settings, enabling transparent re-hashing on next login.
   Also returns True for non-Argon2 hashes (algorithm migration path).

6. **Empty password guard** — `hash("")` raises `PasswordHashingError` immediately,
   before reaching the C library. Defence-in-depth against misconfigured callers.

### What TASK-2.4/2.5 must do

- Call `hasher.needs_rehash(stored_hash)` after every successful login and
  re-hash transparently if True.
- Wrap `hasher.hash()` and `hasher.verify()` in `asyncio.to_thread()` to avoid
  blocking the FastAPI event loop. Both are CPU-bound (not I/O-bound).
- Pass the plaintext password only to `PasswordHasher.hash()` — discard it immediately.
  Never pass it to repositories, domain events, or logging.

---

## Future Work

### CompromisedPasswordChecker (documented, not implemented)

Interface: `app/modules/identity/authentication/domain/services/password_security.py`

Planned adapter: `HibpCompromisedPasswordChecker` using HaveIBeenPwned's
k-anonymity range API (SHA-1 prefix, no full password transmitted). Fails open
if HIBP is unavailable. Applied at registration and password-change time.

### PasswordEntropyEvaluator (documented, not implemented)

Interface: `app/modules/identity/authentication/domain/services/password_security.py`

Planned adapter: `ZxcvbnEntropyEvaluator` using the `zxcvbn` Python port.
Applied alongside `PasswordStrengthPolicy` to produce entropy-aware user feedback.

### MigratingPasswordHasher (not yet designed)

A composite adapter that tries Argon2id first, falls back to bcrypt for
existing hashes, and re-hashes on successful verification. Required if Travix
ever imports users from a bcrypt-based system. Design deferred until a
concrete migration need arises.

---

## Definition of Done

- [x] `Argon2PasswordHasher` implements `PasswordHasher` Protocol (all three methods)
- [x] `Argon2Settings` exposes `from_app_settings()` and `for_testing()`
- [x] `_build_default_hasher()` is cached and logs parameters at INFO level
- [x] `get_password_hasher()` factory and `CurrentPasswordHasher` type alias in place
- [x] Empty password raises `PasswordHashingError` before reaching C library
- [x] Wrong password returns `False` — never raises
- [x] Corrupt hash raises `PasswordHashingError` with message referencing corruption
- [x] Non-Argon2 hash on `verify()` raises `PasswordHashingError` with migration hint
- [x] Non-Argon2 hash on `needs_rehash()` returns `True` (not an error — expected path)
- [x] `PasswordHash.repr` and `str` tested to return `[REDACTED]`
- [x] `CompromisedPasswordChecker` and `PasswordEntropyEvaluator` documented
- [x] `argon2-cffi` added to `pyproject.toml`
- [x] `argon2_*` settings added to `app/config.py`
- [x] All unit tests passing (6 test classes, 40+ cases)
- [x] ADR-004 written and linked to from `pyproject.toml` and `config.py` comments
- [x] Zero framework imports in domain files
- [x] Zero `os.environ` usage
- [x] No secrets hardcoded anywhere
