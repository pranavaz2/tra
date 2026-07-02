# TASK-2.5 — Identity Context: JWT Infrastructure

**Status:** Complete
**Phase:** 2 — Sprint 2
**Depends on:** TASK-2.3 (Password Hashing Infrastructure), TASK-2.4 (Auth API Contract)
**Blocks:** TASK-2.6 (Registration Implementation), TASK-2.7 (Login Implementation)

---

## Objective

Implement the JWT access token infrastructure layer for Travix AI. This is
infrastructure only — no registration, no login, no FastAPI routes, no business
logic, no database operations.

The output is a JWT service that the authentication application layer (TASK-2.6+)
can inject and call without knowing anything about PyJWT or HMAC algorithms.

---

## Scope

### In Scope

- `AccessTokenClaims` and `DecodedAccessToken` frozen dataclasses
- `TokenType` enum (discriminator for cross-type token attack prevention)
- JWT error hierarchy extending `UnauthorizedError` (all → HTTP 401)
- `JWTService` Protocol (domain port)
- `SigningKeyProvider` Protocol with `InMemorySigningKeyProvider` implementation
- `TokenRevocationChecker` Protocol (placeholder — implementation deferred)
- `JWKSProvider` Protocol (placeholder — RS256 migration, ADR-003)
- `HS256JWTService` — concrete implementation using PyJWT
- FastAPI DI: `get_jwt_service()`, `CurrentJWTService` type alias
- `PyJWT[cryptography]>=2.9.0,<3.0.0` added to pyproject.toml
- New settings: `jwt_issuer`, `jwt_audience`, `jwt_leeway_seconds`, `jwt_key_id`
- Comprehensive unit tests

### Explicitly Out of Scope

- Login endpoint implementation
- Registration endpoint implementation
- Logout endpoint implementation
- Token revocation (Redis) — deferred to logout task
- Refresh token implementation (refresh tokens are opaque UUIDs, not JWTs)
- Auth middleware (validates incoming requests)
- RS256 implementation (JWKS interface defined, implementation future)
- Database models or migrations

---

## Files Created / Modified

### Created

| File | Description |
|---|---|
| `app/core/security/jwt/__init__.py` | Package marker with public API docs |
| `app/core/security/jwt/claims.py` | `AccessTokenClaims`, `DecodedAccessToken`, `TokenType` |
| `app/core/security/jwt/errors.py` | JWT error hierarchy (all → 401) |
| `app/core/security/jwt/interfaces.py` | `JWTService`, `SigningKeyProvider`, `TokenRevocationChecker`, `JWKSProvider` protocols |
| `app/core/security/jwt/signing.py` | `SigningKey`, `InMemorySigningKeyProvider` |
| `app/core/security/jwt/service.py` | `HS256JWTService` |
| `app/core/security/jwt/dependencies.py` | `get_jwt_service()`, `CurrentJWTService` |
| `tests/unit/core/security/jwt/test_hs256_jwt_service.py` | Comprehensive unit tests |
| `docs/tasks/TASK-2.5.md` | This file |

### Modified

| File | Change |
|---|---|
| `app/core/security/__init__.py` | Updated placeholder to describe JWT contents |
| `app/config.py` | Added `jwt_issuer`, `jwt_audience`, `jwt_leeway_seconds`, `jwt_key_id` |
| `pyproject.toml` | Added `PyJWT[cryptography]>=2.9.0,<3.0.0` |

---

## Architecture

### Location: `app/core/security/jwt/`

JWT infrastructure is in `app/core/security/` (per CLAUDE.md §5) because it
is a **cross-cutting concern** used by both the identity feature module
(creating tokens after login) and the authentication middleware (validating
tokens on every request). It does not belong inside any single feature module.

### Layer model

```
Auth middleware        → imports JWTService (interface)
Application layer      → imports JWTService (interface) + AccessTokenClaims
Infrastructure layer   → imports HS256JWTService (concrete)
DI factory             → wires Settings → HS256JWTService via JWTService interface
```

### Claims design

```python
# Standard RFC 7519 claims (all required)
sub          # User ID (UUID)
jti          # JWT ID (UUID) — per-token revocation
iat          # Issued at (Unix timestamp)
exp          # Expires at (Unix timestamp)
nbf          # Not before (Unix timestamp)
iss          # Issuer ("https://api.travix.ai")
aud          # Audience ("travix-mobile")

# Travix custom claims (all required)
sid          # Session ID (UUID)
email        # User's email at issuance
verified     # Email verified status at issuance
type         # Token type — always "access" for access tokens
token_version    # Increment → invalidate all user's tokens (no Redis needed)
session_version  # Increment → invalidate this session only
```

JWT header:
```json
{ "alg": "HS256", "typ": "JWT", "kid": "default-v1" }
```

---

## Security Decisions

### 1. Algorithm Pinning (Algorithm Confusion Prevention)

The `alg` header is validated against the configured algorithm BEFORE any key
material is loaded. This prevents algorithm confusion attacks (CVE-style: using
an RS256 token against an HS256 server that mistakenly uses the public key as
the HMAC secret). Only the configured algorithm is accepted.

```python
# In _resolve_verification_key():
if alg != self._ALGORITHM:
    raise JWTAlgorithmError(...)  # before key lookup
```

### 2. `kid` Required in Every Token

All tokens must have a `kid` (key ID) in the header. Tokens without `kid` are
rejected with `JWTMalformedError`. This is required for zero-downtime key
rotation: the receiver looks up the key by `kid` rather than trying every key.

### 3. Constant-Time HMAC Verification

PyJWT delegates HS256 signing and verification to the `cryptography` library
(OpenSSL backend). Signature comparison uses `CRYPTO_memcmp` / constant-time
comparison. Verification is safe against timing side-channels.

### 4. Cross-Type Token Attack Prevention

The `type: "access"` claim is validated after every successful decode. This
prevents a future refresh-JWT from being accepted at an access-token-requiring
endpoint (e.g., if a vulnerability ever allowed refresh token leakage).

### 5. JTI for Per-Token Revocation

Every token carries a `jti` (UUID v4). On logout, the JTI is stored in Redis
with TTL = remaining token lifetime. The auth middleware checks the revocation
list after signature validation. The JWT service has no I/O capabilities — 
revocation is separated into `TokenRevocationChecker` (to be implemented).

### 6. `token_version` and `session_version`

These generation counters enable:
- **token_version**: Force re-login for all devices (increment on password change,
  account compromise). Validated in auth middleware against `AuthenticationCredential.token_version`.
- **session_version**: Invalidate a specific session without revoking its JTI
  (useful when the JTI is unknown, e.g., after a Redis flush). Validated in
  auth middleware against `AuthenticationSession.session_version`.

Neither is validated by the JWT service itself — they are claims the middleware reads.

### 7. `decode_access_token` — Expiry-Tolerant Decode

Two decode methods:
- `verify_access_token`: validates everything. Use in auth middleware.
- `decode_access_token`: signature-verified; skips exp/nbf. Use in logout flows
  where the client's access token may have just expired and the JTI must be
  extracted for Redis revocation. The signature IS still verified.

---

## Key Rotation

### Zero-Downtime Rotation Procedure

1. Generate a new HMAC secret.
2. Update `JWT_KEY_ID` and `JWT_SECRET_KEY` in the environment.
3. Pass the old key as an additional key in `InMemorySigningKeyProvider`.
4. Deploy. New tokens use the new `kid`; old tokens verify against the old key.
5. After 15 minutes (max token lifetime), remove the old key.

### `InMemorySigningKeyProvider` API

```python
InMemorySigningKeyProvider(
    primary_key,         # is_primary=True, used for signing
    *legacy_keys,        # is_primary=False, available for verification only
)
```

### Future Key Providers

`SigningKeyProvider` is a Protocol. Future implementations:
- `SecretsManagerSigningKeyProvider` — reads from AWS Secrets Manager
- `KMSSigningKeyProvider` — uses AWS KMS (key material never leaves KMS)
- `VaultSigningKeyProvider` — reads from HashiCorp Vault

---

## Future Impact

### TASK-2.6 (Registration)
After email verification or auto-login, build `AccessTokenClaims` and call
`jwt_service.create_access_token(claims)`. Inject `CurrentJWTService`.

### TASK-2.7 (Login)
Same as registration: build claims, call `create_access_token`.

### Logout
Call `jwt_service.decode_access_token(token)` (tolerates expiry) to extract
`claims.jti` and `claims.sid`, then add JTI to Redis revocation list.

### Auth Middleware
Call `jwt_service.verify_access_token(token)` on every protected request.
After signature validation, check `TokenRevocationChecker.is_revoked(claims.jti)`.
After revocation check, validate `claims.token_version` and `claims.session_version`
against the database (or Redis cache).

### Refresh Token Flow
Refresh tokens are opaque UUID strings (not JWTs) stored in PostgreSQL.
After successful refresh, call `jwt_service.create_access_token()` to issue
a new access token. JWT service is NOT involved in refresh token validation.

### OAuth / Passkeys / Magic Links
All authentication methods converge at `jwt_service.create_access_token(claims)`.
The JWT service interface is stable for all future auth methods.

### RS256 Migration (ADR-003)
Implement `RS256JWTService` following the `JWTService` Protocol.
Change `_build_jwt_service()` in `dependencies.py` to return `RS256JWTService`.
Add `JWKSProvider` implementation and `GET /auth/.well-known/jwks.json` endpoint.
No changes to callers (login, middleware, logout) — they depend on `JWTService`.

---

## Security Review Notes (Principal Security Engineer)

### Improvements Made vs. Naive Implementation

1. Algorithm is pinned and validated before key lookup (algorithm confusion prevention).
2. `kid` is required — no fallback to "try all keys" which would be O(n) and confusing.
3. `type` claim validated post-decode, not by PyJWT (PyJWT doesn't know about custom types).
4. `verify_access_token` vs `decode_access_token` clearly named — hard to misuse.
5. `SigningKey.secret` is `SecretStr` — never in repr, never logged.
6. `DecodedAccessToken.raw_token` has `field(repr=False)` — JWT string never in repr.
7. PyJWT `algorithms=["HS256"]` prevents dynamic algorithm selection from header.
8. `_REQUIRED_STANDARD_CLAIMS` explicitly listed — missing claims are rejected.
9. `leeway_seconds=0` in tests — no clock skew tolerance by default in tests.
10. Exception chaining: all `raise ... from exc` — original PyJWT error preserved for debugging.

### Remaining TODOs

- [ ] `TokenRevocationChecker` has no implementation yet (requires Redis infrastructure task).
- [ ] Auth middleware that calls `verify_access_token` on every request does not exist yet.
- [ ] `token_version` and `session_version` are not yet validated by middleware.
- [ ] `JWKSProvider` placeholder — to be implemented when migrating to RS256 (ADR-003).
- [ ] `SecretsManagerSigningKeyProvider` — production-grade key storage for cloud deployment.

---

## Definition of Done

- [x] `AccessTokenClaims` frozen dataclass with all required fields
- [x] `DecodedAccessToken` frozen dataclass; `raw_token` excluded from repr
- [x] `TokenType` enum with `ACCESS = "access"`
- [x] JWT error hierarchy: `JWTError` → 12 subclasses, all extend `UnauthorizedError`
- [x] `JWTService` Protocol with docstrings documenting failure modes
- [x] `SigningKeyProvider` Protocol
- [x] `TokenRevocationChecker` Protocol (placeholder with Redis design documented)
- [x] `JWKSProvider` Protocol (placeholder with RS256 migration documented)
- [x] `InMemorySigningKeyProvider` with multi-key rotation support
- [x] `HS256JWTService`: algorithm pinning, kid resolution, claim validation, error mapping
- [x] `verify_access_token` (full) and `decode_access_token` (expiry-tolerant)
- [x] `create_access_token` with kid in JWT header
- [x] `validate_claims` for in-memory pre-encode validation
- [x] `get_jwt_service()` factory + `CurrentJWTService` DI alias
- [x] `PyJWT[cryptography]` added to pyproject.toml
- [x] `jwt_issuer`, `jwt_audience`, `jwt_leeway_seconds`, `jwt_key_id` added to Settings
- [x] Unit tests: 40+ test cases across 8 test classes
- [x] All new files have type hints on every function signature
- [x] No `os.environ` usage — all config via `get_settings()`
- [x] No secrets in any source file
- [x] Architecture: no feature module imports PyJWT directly
- [x] ADR-003 referenced (no new ADR required — decisions documented in this file)
