# Authentication Application Layer

**Status:** Not yet implemented — placeholder for Sprint 2 / TASK-2.2.

## Purpose

Use cases and application services that orchestrate the authentication domain.
This layer has no HTTP knowledge — it receives domain objects and returns
`Result[T]` values that the API layer maps to HTTP responses.

## Planned files

| File | Purpose |
|---|---|
| `use_cases/register_user.py` | `RegisterUserUseCase` |
| `use_cases/login_user.py` | `LoginUserUseCase` |
| `use_cases/refresh_session.py` | `RefreshSessionUseCase` |
| `use_cases/logout_user.py` | `LogoutUserUseCase` |
| `use_cases/logout_all_sessions.py` | `LogoutAllSessionsUseCase` |
| `use_cases/verify_email.py` | `VerifyEmailUseCase` |
| `use_cases/change_password.py` | `ChangePasswordUseCase` |
| `dtos.py` | Input / output data transfer objects for use cases |

## Responsibilities

- Coordinate between `AuthenticationRepository`, `SessionRepository`,
  and external services (email notifications, Redis token revocation).
- Enforce the `AuthenticationPolicy` and `SessionPolicy` rules.
- Publish domain events via the event bus.
- Return `Result[T]` — never raise HTTP exceptions.

## Constraints

- No FastAPI imports.
- No SQLAlchemy imports.
- No bcrypt / JWT / Redis imports — those go in the infrastructure layer.
