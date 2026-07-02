# ADR-004 — Argon2id as the Password Hashing Algorithm

| Field | Value |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-06-26 |
| **Deciders** | Principal Security Engineer |
| **Task** | TASK-2.3 |

---

## Context

Travix AI stores user credentials. Every stored password hash must satisfy
the following security properties:

1. **Offline-attack resistance** — an attacker with the database must not be
   able to crack passwords quickly, even with modern GPU hardware.
2. **Side-channel resistance** — verification must run in constant time to
   prevent timing-based oracle attacks.
3. **Future-proof** — the algorithm must be replaceable without forcing users
   to reset their passwords (transparent rehash on next login).
4. **Ecosystem trust** — the algorithm must be standardised, well-audited,
   and actively maintained.

The options evaluated were **bcrypt**, **scrypt**, **PBKDF2-HMAC-SHA256**,
and **Argon2id** (IETF RFC 9106, winner of the 2015 Password Hashing Competition).

---

## Decision

**Use Argon2id** as the canonical password hashing algorithm for all
password-based credentials in Travix AI.

Implementation: `argon2-cffi` Python library (wraps the reference C implementation).

Production defaults (configurable via environment variables):

| Parameter | Default | Environment Variable |
|---|---|---|
| Algorithm type | Argon2id | — (fixed) |
| Time cost (iterations) | 3 | `ARGON2_TIME_COST` |
| Memory cost | 65536 KiB (64 MiB) | `ARGON2_MEMORY_COST` |
| Parallelism (lanes) | 4 | `ARGON2_PARALLELISM` |
| Hash length | 32 bytes (256-bit) | `ARGON2_HASH_LEN` |
| Salt length | 16 bytes (128-bit) | `ARGON2_SALT_LEN` |

These defaults meet OWASP's 2024 Argon2id recommendation:
memory ≥ 64 MiB, iterations ≥ 2, parallelism ≥ 1.

---

## Rationale

### Why Argon2id over bcrypt?

| Property | bcrypt | Argon2id |
|---|---|---|
| Memory-hardness | No | Yes — resists GPU/ASIC attacks |
| Time-memory tradeoff resistance | Weak | Strong (id variant) |
| Password length limit | 72 bytes (silent truncation) | None |
| Side-channel resistance | Partial | Full (constant-time in C ref impl) |
| NIST status | Legacy | SP 800-132 recommended |
| IETF RFC | None | RFC 9106 |
| PHC winner | No | Yes (2015) |

bcrypt's 72-byte truncation is a silent security footgun: a user who sets a
100-character password believes it is strong; bcrypt silently truncates it.
Argon2id has no such limit.

### Why Argon2id over Argon2i or Argon2d?

- **Argon2i** — optimised against side-channel attacks but vulnerable to
  time-memory tradeoffs. Suitable for key derivation, not password hashing.
- **Argon2d** — maximally memory-hard but vulnerable to side-channel attacks.
  Suitable for applications without privileged attacker access.
- **Argon2id** — hybrid: uses Argon2i's memory access pattern in the first
  half and Argon2d's in the second half. Resists both side-channel and
  time-memory tradeoff attacks. RFC 9106 recommends Argon2id for password
  hashing in all contexts where the attacker may have unprivileged access
  to the hashing machine (i.e., cloud/shared hosting). **This is our context.**

### Why argon2-cffi?

- Wraps the reference C implementation (speed + correctness).
- PHC string format (e.g., `$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>`) encodes
  all parameters in the hash string itself. The verifier never needs out-of-band
  parameter storage.
- `PasswordHasher.check_needs_rehash()` detects parameter upgrades automatically.
- Actively maintained; Python 3.12 compatible.
- Zero external C dependencies beyond the bundled Argon2 C library.

### Parameter selection rationale

**Time cost = 3:** OWASP minimum is 2. We use 3 to provide a small safety margin.
This produces ~150–200 ms latency on a 4-core 2024 API server with 64 MiB memory
allocated — acceptable for a login flow.

**Memory cost = 65536 KiB (64 MiB):** OWASP recommendation. Forces attackers to
allocate 64 MiB per hash attempt on GPU, reducing parallelism from thousands of
threads to dozens per GB of VRAM.

**Parallelism = 4:** Matches the typical API server core count. Higher values do not
improve security beyond the memory-cost effect; they only increase CPU utilisation
during hashing.

**Hash length = 32 bytes:** 256-bit output. Collision resistance is 2^128 (birthday
bound), far beyond any foreseeable attack.

**Salt length = 16 bytes:** 128-bit random salt. Probability of collision across
10^9 users is negligible (~10^-19). argon2-cffi generates the salt internally using
`os.urandom()`.

---

## Migration Path

### Transparent rehash on next login

The `needs_rehash()` method returns `True` for:
1. Hashes produced with lower parameters (time_cost, memory_cost, parallelism).
2. Hashes in a non-Argon2 format (e.g., bcrypt).

On every successful login:
```
1. Verify password with current hasher.
2. If needs_rehash(stored_hash):
       new_hash = hasher.hash(plain_password)
       credential.change_password(new_hash)
       repository.save(credential)
3. Return session token.
```

Users never notice the upgrade. No forced password reset.

### Parameter tuning (future)

When server hardware improves, increase `ARGON2_TIME_COST` or
`ARGON2_MEMORY_COST` in the environment. All existing hashes will be
flagged by `needs_rehash()` and upgraded transparently on next login.

### Algorithm replacement (future)

If Argon2id is ever superseded, create a new `XyzPasswordHasher` implementing
the `PasswordHasher` domain port. The `MigratingPasswordHasher` (a composite
adapter, not yet implemented) will:
1. Try verification with the new hasher.
2. Fall back to the old hasher if `InvalidHashError` is raised.
3. Re-hash with the new hasher on successful verification.

**No domain code changes required** — only a new infrastructure adapter.

---

## Consequences

### Positive

- Passwords are resistant to GPU offline attacks (memory-hard).
- No silent truncation (Argon2 has no bcrypt 72-byte limit).
- Transparent parameter upgrades via `needs_rehash()`.
- PHC string format is self-describing — no out-of-band parameter storage.
- `PasswordHash` value object is algorithm-agnostic — domain is not coupled to Argon2.

### Negative / Trade-offs

- Each hash requires 64 MiB of server RAM for the duration of the operation.
  Under heavy registration/login load, this can cause memory pressure.
  **Mitigation:** ARQ task queue for background re-hashing; rate limiting on
  login and registration endpoints; and monitoring on memory metrics.
- `argon2-cffi` adds a compiled C extension dependency. Alpine Linux Docker
  images need `gcc` and `musl-dev` in the build stage.
  **Mitigation:** documented in `infrastructure/docker/Dockerfile`.
- Higher latency per hash (~150–200 ms at production params) compared to
  PBKDF2 (~5 ms). Intentional — this is the security property we want.
  **Mitigation:** rate limiting on auth endpoints prevents DoS amplification.

### Neutral

- `argon2-cffi>=23.1.0` is pinned in `pyproject.toml`. Major version upgrades
  require review of the PHC format compatibility.
- The `PasswordHasher` domain Protocol is synchronous (CPU-bound); the
  application layer wraps calls in `asyncio.to_thread()` to avoid blocking
  the event loop. This is documented in the domain port's docstring.
