"""
Travix AI — Authorization Infrastructure

FastAPI dependency-based authorization for protected routes.
No ASGI middleware — authorization is route-specific via DI.

Contents:
  context.py     AuthorizationContext frozen dataclass (user_id, session_id, JTI, …)
  errors.py      RFC 7807 error builders + AuthorizationError exception
  revocation.py  NullTokenRevocationChecker placeholder (TASK-2.12 → Redis impl)
  dependencies.py All injectable auth dependencies:
                   RequireAuthentication, OptionalAuthentication,
                   CurrentUser, CurrentSession, CurrentAccessToken
"""
