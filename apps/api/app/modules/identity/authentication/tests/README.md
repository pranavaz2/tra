# Authentication Tests

**Status:** Domain unit tests are ready to be written once TASK-2.1 is complete.
Integration and API tests require TASK-2.2 / TASK-2.3.

## Test structure

```
tests/
├── unit/
│   └── identity/
│       └── authentication/
│           ├── test_credential.py       # AuthenticationCredential aggregate
│           ├── test_session.py          # AuthenticationSession aggregate
│           ├── test_email_vo.py         # Email value object
│           ├── test_password_hash_vo.py # PasswordHash value object
│           ├── test_specifications.py   # ValidEmail, StrongPassword, ActiveSession specs
│           └── test_domain_events.py    # Event construction and immutability
└── integration/
    └── identity/
        └── authentication/
            ├── test_authentication_repository.py
            ├── test_session_repository.py
            └── test_auth_use_cases.py
```

## Domain unit test approach

Domain tests have **zero infrastructure dependencies** — no database, no Redis,
no bcrypt, no JWT. They instantiate domain objects directly using test fixtures.

Riverpod equivalent: use plain Python `pytest` fixtures to inject test doubles
that satisfy the Policy Protocols (e.g., `MockPasswordPolicy`).

## Key test scenarios

- `AuthenticationCredential.create()` emits `UserRegistered`
- `AuthenticationCredential.record_failed_login()` locks after N attempts
- `AuthenticationCredential.change_password()` fails on disabled account
- `AuthenticationSession.rotate_refresh_token()` fails on expired session
- `AuthenticationSession.revoke()` is idempotent
- `Email` normalises and rejects invalid formats
- `PasswordHash` redacts itself in repr / str
