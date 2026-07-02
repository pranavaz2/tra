# Authentication Infrastructure Layer

**Status:** Not yet implemented — placeholder for Sprint 2 / TASK-2.2.

## Purpose

Implements all infrastructure concerns for the Authentication bounded context:
database persistence, token generation, password hashing, and Redis integration.

## Planned files

| File | Purpose |
|---|---|
| `models.py` | SQLAlchemy ORM models for `authentication_credentials` and `authentication_sessions` |
| `repositories.py` | `SQLAlchemyAuthenticationRepository` and `SQLAlchemySessionRepository` |
| `password_hasher.py` | bcrypt adapter — implements `PasswordHasher` protocol |
| `token_service.py` | JWT access-token creation and verification |
| `token_revocation.py` | Redis-backed token blacklist (CLAUDE.md §11) |
| `policies.py` | Concrete `PasswordPolicy`, `SessionPolicy`, `AuthenticationPolicy` implementations reading from settings |
| `dependencies.py` | FastAPI dependency factories for all infrastructure objects |

## Database tables

| Table | Description |
|---|---|
| `authentication_credentials` | One row per user: email, password_hash, flags, timestamps |
| `authentication_sessions` | One row per active session: user_id FK, refresh_token_id, expiry |

## Security constraints (from CLAUDE.md §11)

- JWT access tokens: 15-minute maximum lifetime.
- Refresh tokens: 7-day expiry, stored in PostgreSQL, support explicit revocation.
- Redis token revocation blacklist — Redis DB 2 with AOF persistence (loss = security vulnerability).
- Refresh token rotation: every `/auth/refresh` issues a new token and invalidates the previous.
- Reuse of a superseded refresh token triggers full token-family invalidation.
- Never store tokens in plain text — store only the `RefreshTokenId` (UUID), not the token bytes.
