"""
FastAPI dependency providers — Authentication Infrastructure.

Exposes domain port implementations as injectable dependencies following
the pattern established in app.dependencies:
    Annotated[InterfaceType, Depends(factory_fn)]

Consumers import the type alias and declare it in their function signature:

    from app.modules.identity.authentication.infrastructure.dependencies import (
        CurrentPasswordHasher,
        CurrentRefreshTokenService,
        CurrentRegistrationService,
    )

    async def register_user(
        body: RegisterRequest,
        registration: CurrentRegistrationService,
    ) -> ...:
        command = RegisterUserCommand(email=body.email, password=body.password)
        result = await registration.execute(command)
        ...

Singleton strategy:
  - Stateless adapters (PasswordHasher, RefreshTokenGenerator, RefreshTokenHasher,
    Clock, UUIDProvider, policies) are cached via lru_cache or module singletons.
  - Stateful in-memory stores (InMemoryRefreshTokenStore, InMemorySessionRepository)
    are module-level singletons — one shared instance per process.
  - InMemoryUnitOfWork is created per-request (not cached) so each request gets
    a fresh transaction boundary.
  - In production, replace in-memory stores with PostgreSQL-backed implementations
    that accept an AsyncSession dependency.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import get_settings
from app.core.security.jwt.dependencies import CurrentJWTService, get_jwt_service
from app.core.security.jwt.interfaces import JWTService
from app.modules.identity.authentication.application.interfaces import (
    LoginService,
    RefreshTokenService,
    RegistrationService,
)
from app.modules.identity.authentication.application.refresh_token_service import (
    RefreshTokenApplicationService,
)
from app.modules.identity.authentication.application.login_handler import LoginUserHandler
from app.modules.identity.authentication.application.login_service import (
    LoginConfiguration,
    LoginService as LoginServiceImpl,
)
from app.modules.identity.authentication.application.registration_handler import (
    RegisterUserHandler,
)
from app.modules.identity.authentication.application.registration_service import (
    RegistrationConfiguration,
    RegistrationService as RegistrationServiceImpl,
)
from app.modules.identity.authentication.domain.repositories.interfaces import (
    AuthenticationRepository,
    RefreshTokenRepository,
    SessionRepository,
)
from app.modules.identity.authentication.domain.services.password_hasher import PasswordHasher
from app.modules.identity.authentication.domain.services.password_policies import (
    PasswordStrengthPolicy,
)
from app.modules.identity.authentication.domain.services.policies import (
    AuthenticationPolicy,
    SessionPolicy,
)
from app.modules.identity.authentication.domain.services.refresh_token_protocols import (
    RefreshTokenGenerator,
    RefreshTokenHasher,
)
from app.modules.identity.authentication.infrastructure.event_publisher import (
    LoggingEventPublisher,
)
from app.modules.identity.authentication.infrastructure.password_hasher import (
    _build_default_hasher,
)
from app.modules.identity.authentication.infrastructure.policies import (
    DefaultAuthenticationPolicy,
    DefaultPasswordStrengthPolicy,
    DefaultSessionPolicy,
)
from app.modules.identity.authentication.infrastructure.refresh_token_generator import (
    SecureRefreshTokenGenerator,
)
from app.modules.identity.authentication.infrastructure.refresh_token_hasher import (
    Sha256RefreshTokenHasher,
)
from app.modules.identity.authentication.infrastructure.refresh_token_store import (
    InMemoryRefreshTokenStore,
    InMemorySessionRepository,
)
from app.modules.identity.authentication.infrastructure.auth_repository import (
    InMemoryAuthRepository,
)
from app.modules.identity.authentication.infrastructure.unit_of_work import InMemoryUnitOfWork
from app.shared.domain.clock import SystemClock
from app.shared.domain.event_publisher import EventPublisher
from app.shared.domain.unit_of_work import UnitOfWork
from app.shared.domain.uuid_provider import StandardUUIDProvider, UUIDProvider

# ---------------------------------------------------------------------------
# Password hasher
# ---------------------------------------------------------------------------


def get_password_hasher() -> PasswordHasher:
    """
    Return the singleton Argon2PasswordHasher.

    The hasher is constructed once (lru_cache) and reused across all requests.
    Consumers depend only on the PasswordHasher Protocol.
    """
    return _build_default_hasher()


CurrentPasswordHasher = Annotated[PasswordHasher, Depends(get_password_hasher)]
"""
Injectable PasswordHasher. Override in tests:

    app.dependency_overrides[get_password_hasher] = lambda: MockPasswordHasher()
"""

# ---------------------------------------------------------------------------
# Refresh token generator
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_token_generator() -> SecureRefreshTokenGenerator:
    return SecureRefreshTokenGenerator()


def get_refresh_token_generator() -> RefreshTokenGenerator:
    """Return the cached SecureRefreshTokenGenerator singleton."""
    return _build_token_generator()


CurrentRefreshTokenGenerator = Annotated[
    RefreshTokenGenerator, Depends(get_refresh_token_generator)
]

# ---------------------------------------------------------------------------
# Refresh token hasher
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_token_hasher() -> Sha256RefreshTokenHasher:
    return Sha256RefreshTokenHasher()


def get_refresh_token_hasher() -> RefreshTokenHasher:
    """Return the cached Sha256RefreshTokenHasher singleton."""
    return _build_token_hasher()


CurrentRefreshTokenHasher = Annotated[RefreshTokenHasher, Depends(get_refresh_token_hasher)]

# ---------------------------------------------------------------------------
# In-memory token store and session repository (dev/test)
#
# Replace with PostgreSQL-backed implementations in TASK-2.7:
#   async def get_refresh_token_store(db=Depends(get_db_session)) -> RefreshTokenRepository:
#       return PostgresRefreshTokenRepository(db)
# ---------------------------------------------------------------------------

_token_store_singleton = InMemoryRefreshTokenStore()
_session_repo_singleton = InMemorySessionRepository()


def get_refresh_token_store() -> RefreshTokenRepository:
    """
    Return the in-memory RefreshTokenRepository singleton.

    TASK-2.7: Replace with PostgresRefreshTokenRepository(db_session).
    """
    return _token_store_singleton


def get_session_repository() -> SessionRepository:
    """
    Return the in-memory SessionRepository singleton.

    TASK-2.7: Replace with PostgresSessionRepository(db_session).
    """
    return _session_repo_singleton


CurrentRefreshTokenStore = Annotated[RefreshTokenRepository, Depends(get_refresh_token_store)]
CurrentSessionRepository = Annotated[SessionRepository, Depends(get_session_repository)]

# ---------------------------------------------------------------------------
# RefreshTokenApplicationService
# ---------------------------------------------------------------------------


def get_refresh_token_service(
    token_store: CurrentRefreshTokenStore,
    session_repo: CurrentSessionRepository,
    generator: CurrentRefreshTokenGenerator,
    hasher: CurrentRefreshTokenHasher,
) -> RefreshTokenService:
    """Build a RefreshTokenApplicationService with all dependencies injected."""
    settings = get_settings()
    return RefreshTokenApplicationService(
        token_store=token_store,
        session_repository=session_repo,
        generator=generator,
        hasher=hasher,
        token_lifetime_days=settings.jwt_refresh_token_expire_days,
    )


CurrentRefreshTokenService = Annotated[RefreshTokenService, Depends(get_refresh_token_service)]
"""
Injectable RefreshTokenService. Override in tests:

    app.dependency_overrides[get_refresh_token_service] = lambda: MockRefreshTokenService()
"""

# ---------------------------------------------------------------------------
# In-memory AuthenticationRepository (dev/test placeholder)
# Replace with PostgresAuthenticationRepository(db_session) in production.
# ---------------------------------------------------------------------------

_auth_repo_singleton = InMemoryAuthRepository()


def get_auth_repository() -> AuthenticationRepository:
    """
    Return the in-memory AuthenticationRepository singleton.

    Production: replace with PostgresAuthenticationRepository(db_session).
    """
    return _auth_repo_singleton


CurrentAuthRepository = Annotated[AuthenticationRepository, Depends(get_auth_repository)]

# ---------------------------------------------------------------------------
# Shared kernel: Clock, UUIDProvider, UnitOfWork, EventPublisher
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_system_clock() -> SystemClock:
    return SystemClock()


def get_clock() -> SystemClock:
    return _build_system_clock()


@lru_cache(maxsize=1)
def _build_uuid_provider() -> StandardUUIDProvider:
    return StandardUUIDProvider()


def get_uuid_provider() -> UUIDProvider:
    return _build_uuid_provider()


def get_unit_of_work() -> UnitOfWork:
    """Return a fresh InMemoryUnitOfWork per request."""
    return InMemoryUnitOfWork()


@lru_cache(maxsize=1)
def _build_event_publisher() -> LoggingEventPublisher:
    return LoggingEventPublisher()


def get_event_publisher() -> EventPublisher:
    return _build_event_publisher()


CurrentUnitOfWork = Annotated[UnitOfWork, Depends(get_unit_of_work)]
CurrentEventPublisher = Annotated[EventPublisher, Depends(get_event_publisher)]

# ---------------------------------------------------------------------------
# Policy implementations
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_strength_policy() -> DefaultPasswordStrengthPolicy:
    return DefaultPasswordStrengthPolicy()


def get_strength_policy() -> PasswordStrengthPolicy:
    return _build_strength_policy()


@lru_cache(maxsize=1)
def _build_session_policy() -> DefaultSessionPolicy:
    settings = get_settings()
    return DefaultSessionPolicy(session_ttl_days=settings.jwt_refresh_token_expire_days)


def get_session_policy() -> SessionPolicy:
    return _build_session_policy()


@lru_cache(maxsize=1)
def _build_auth_policy() -> DefaultAuthenticationPolicy:
    settings = get_settings()
    return DefaultAuthenticationPolicy(
        require_email_verification=settings.registration_require_email_verification,
    )


def get_auth_policy() -> AuthenticationPolicy:
    return _build_auth_policy()


CurrentStrengthPolicy = Annotated[PasswordStrengthPolicy, Depends(get_strength_policy)]
CurrentSessionPolicy = Annotated[SessionPolicy, Depends(get_session_policy)]
CurrentAuthPolicy = Annotated[AuthenticationPolicy, Depends(get_auth_policy)]

# ---------------------------------------------------------------------------
# RegistrationConfiguration
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_registration_config() -> RegistrationConfiguration:
    settings = get_settings()
    return RegistrationConfiguration(
        auto_verify_email=settings.registration_auto_verify_email,
        access_token_lifetime_minutes=settings.jwt_access_token_expire_minutes,
        jwt_issuer=settings.jwt_issuer,
        jwt_audience=settings.jwt_audience,
    )


def get_registration_config() -> RegistrationConfiguration:
    return _build_registration_config()


# ---------------------------------------------------------------------------
# RegistrationService and RegisterUserHandler
# ---------------------------------------------------------------------------


def get_registration_service(
    auth_repo: CurrentAuthRepository,
    session_repo: CurrentSessionRepository,
    refresh_token_svc: CurrentRefreshTokenService,
    jwt_svc: CurrentJWTService,
    hasher: CurrentPasswordHasher,
    strength_policy: CurrentStrengthPolicy,
    session_policy: CurrentSessionPolicy,
    auth_policy: CurrentAuthPolicy,
    uow: CurrentUnitOfWork,
    event_publisher: CurrentEventPublisher,
) -> RegistrationService:
    """Build a RegistrationService with all dependencies injected."""
    return RegistrationServiceImpl(
        auth_repository=auth_repo,
        session_repository=session_repo,
        refresh_token_service=refresh_token_svc,
        jwt_service=jwt_svc,
        password_hasher=hasher,
        strength_policy=strength_policy,
        session_policy=session_policy,
        auth_policy=auth_policy,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=get_uuid_provider(),
        clock=get_clock(),
        config=get_registration_config(),
    )


CurrentRegistrationService = Annotated[RegistrationService, Depends(get_registration_service)]
"""
Injectable RegistrationService. Override in tests:

    app.dependency_overrides[get_registration_service] = lambda: MockRegistrationService()
"""


def get_registration_handler(
    service: CurrentRegistrationService,
) -> RegisterUserHandler:
    """Build the command handler backed by the injected RegistrationService."""
    return RegisterUserHandler(service=service)


CurrentRegistrationHandler = Annotated[RegisterUserHandler, Depends(get_registration_handler)]


# ---------------------------------------------------------------------------
# LoginConfiguration
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _build_login_config() -> LoginConfiguration:
    settings = get_settings()
    return LoginConfiguration(
        access_token_lifetime_minutes=settings.jwt_access_token_expire_minutes,
        jwt_issuer=settings.jwt_issuer,
        jwt_audience=settings.jwt_audience,
    )


def get_login_config() -> LoginConfiguration:
    return _build_login_config()


# ---------------------------------------------------------------------------
# LoginService and LoginUserHandler
# ---------------------------------------------------------------------------


def get_login_service(
    auth_repo: CurrentAuthRepository,
    session_repo: CurrentSessionRepository,
    refresh_token_svc: CurrentRefreshTokenService,
    jwt_svc: CurrentJWTService,
    hasher: CurrentPasswordHasher,
    session_policy: CurrentSessionPolicy,
    auth_policy: CurrentAuthPolicy,
    uow: CurrentUnitOfWork,
    event_publisher: CurrentEventPublisher,
) -> LoginService:
    """Build a LoginService with all dependencies injected."""
    return LoginServiceImpl(
        auth_repository=auth_repo,
        session_repository=session_repo,
        refresh_token_service=refresh_token_svc,
        jwt_service=jwt_svc,
        password_hasher=hasher,
        session_policy=session_policy,
        auth_policy=auth_policy,
        unit_of_work=uow,
        event_publisher=event_publisher,
        uuid_provider=get_uuid_provider(),
        clock=get_clock(),
        config=get_login_config(),
    )


CurrentLoginService = Annotated[LoginService, Depends(get_login_service)]
"""
Injectable LoginService. Override in tests:

    app.dependency_overrides[get_login_service] = lambda: MockLoginService()
"""


def get_login_handler(
    service: CurrentLoginService,
) -> LoginUserHandler:
    """Build the login command handler backed by the injected LoginService."""
    return LoginUserHandler(service=service)


CurrentLoginHandler = Annotated[LoginUserHandler, Depends(get_login_handler)]
