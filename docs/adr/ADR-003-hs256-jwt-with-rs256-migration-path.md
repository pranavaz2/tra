# ADR-003: HS256 JWT with Planned RS256 Migration Path

| Field       | Value                        |
|-------------|------------------------------|
| **Status**  | Accepted                     |
| **Date**    | 2026-06-26                   |
| **Deciders**| Engineering Team             |

---

## Context

Travix AI uses short-lived JWT access tokens (15-minute expiry) for API authentication.
We need to choose a signing algorithm. The primary candidates are:

1. **HS256 (HMAC-SHA256)** — symmetric algorithm. The same secret key is used to both sign
   and verify tokens.
2. **RS256 (RSA-SHA256)** — asymmetric algorithm. A private key signs tokens; any holder
   of the public key can verify them without being able to issue new tokens.

## Decision

We will use **HS256** for the initial implementation, with a documented migration path to
RS256 when the architecture requires it.

## Rationale

### Why HS256 now

**Architectural fit** — in the current architecture, the single FastAPI service is both the
token issuer and the token verifier. When a client presents a token, the same service that
issued it validates it. There is no scenario where a separate service needs to verify tokens
without being trusted with the signing key. The asymmetry benefit of RS256 — separating
signing authority from verification authority — does not apply.

**Operational simplicity** — HS256 requires a single `JWT_SECRET_KEY` environment variable.
RS256 requires managing an RSA key pair: generating the keypair, securely storing the private
key, distributing the public key, rotating both keys on a schedule, and publishing a JWKS
endpoint for key discovery. This operational overhead is premature for a single-service
deployment.

**Token validity is 15 minutes** — the short access token lifetime significantly limits the
blast radius of a compromised signing key. A stolen HS256 key allows an attacker to forge
tokens, but only for 15 minutes per token. Token revocation via Redis ensures immediate
invalidation on logout or suspicious activity.

**Refresh token rotation** — the real protection against stolen credentials is the refresh
token rotation system. Every use of a refresh token invalidates the previous one. Reuse of
a superseded refresh token revokes the entire token family immediately. This mechanism
provides stolen-token detection independent of the signing algorithm.

### Why not RS256 now

- No external services verify Travix AI tokens — there is no JWKS consumer.
- Key rotation for RSA requires a grace period where both old and new keys are valid.
  Implementing a JWKS endpoint and key rotation schedule before they are needed adds
  complexity without benefit.
- The performance difference (RSA signature verification is ~10x slower than HMAC) is
  irrelevant at current scale but would matter at high throughput.

### RS256 migration triggers

RS256 becomes the correct choice when any of the following are true:

1. **A downstream service needs to verify tokens independently** — e.g., an Edge function,
   a mobile BFF, or a third-party integration that should be able to verify token authenticity
   without access to the signing secret.
2. **Multiple issuers** — if the auth service becomes a separate deployment from the
   resource API, the resource API should hold only the public key.
3. **JWKS endpoint required** — if the product integrates with an OAuth 2.0 Authorization
   Server or OpenID Connect provider that requires a JWKS endpoint for key discovery.

## Migration Path

The migration from HS256 to RS256 is designed to be non-breaking:

1. Generate an RSA keypair (minimum 2048-bit, recommend 4096-bit for new systems).
2. Implement a `/auth/.well-known/jwks.json` endpoint exposing the public key.
3. Update the token issuer to sign with the RSA private key.
4. Update the token verifier to accept both HS256 tokens (for the grace period) and
   RS256 tokens. All newly issued tokens use RS256.
5. After the HS256 token max-age (15 minutes) has elapsed, disable HS256 acceptance.
6. Remove the HS256 secret from the configuration.

The grace period is 15 minutes because that is the maximum access token lifetime. No
active session is disrupted by the migration.

## Consequences

### Positive
- Simpler initial implementation — one secret key, no key management infrastructure.
- Fully compatible with the documented migration path.
- Refresh token rotation provides stolen-token detection independent of signing algorithm.

### Negative / Mitigations
- **Symmetric key exposure** — any system component that verifies tokens also holds the
  signing secret. Mitigation: in the current architecture, only the API verifies tokens. The
  key is never distributed to the mobile app or third parties. Strict secret management via
  environment variables and CI/CD secrets prevents key leakage.
- **Migration required for multi-service** — if the architecture evolves to multiple services,
  migration is mandatory. Mitigation: the migration path is documented here and is
  straightforward given the 15-minute token lifetime.
