"""
FastAPI dependency injection for the JWT service.

Usage in route handlers and middleware:

    from app.core.security.jwt.dependencies import CurrentJWTService

    @router.post("/protected")
    async def protected(jwt_service: CurrentJWTService) -> ...:
        decoded = jwt_service.verify_access_token(token)
        ...

The singleton is cached after the first call. In tests, override via:

    app.dependency_overrides[get_jwt_service] = lambda: MockJWTService()

Or clear the cache and set environment variables:

    from app.core.security.jwt.dependencies import _build_jwt_service
    _build_jwt_service.cache_clear()
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import get_settings
from app.core.security.jwt.interfaces import JWTService
from app.core.security.jwt.service import HS256JWTService
from app.core.security.jwt.signing import InMemorySigningKeyProvider, SigningKey


@lru_cache(maxsize=1)
def _build_jwt_service() -> HS256JWTService:
    """
    Build and cache the JWT service singleton.

    Reads configuration at first call. In tests, call _build_jwt_service.cache_clear()
    before changing environment variables.
    """
    settings = get_settings()
    key_provider = InMemorySigningKeyProvider(
        SigningKey(
            kid=settings.jwt_key_id,
            algorithm=settings.jwt_algorithm,
            secret=settings.jwt_secret_key,
            is_primary=True,
        )
    )
    return HS256JWTService(
        signing_key_provider=key_provider,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        algorithm=settings.jwt_algorithm,
        leeway_seconds=settings.jwt_leeway_seconds,
        access_token_lifetime_minutes=settings.jwt_access_token_expire_minutes,
    )


def get_jwt_service() -> JWTService:
    """Return the cached JWT service singleton. Override in tests via dependency_overrides."""
    return _build_jwt_service()


CurrentJWTService = Annotated[JWTService, Depends(get_jwt_service)]
"""
Typed FastAPI dependency for the JWT service.

    from app.core.security.jwt.dependencies import CurrentJWTService

    async def my_route(jwt_service: CurrentJWTService) -> ...:
        ...
"""
