"""
JWT Infrastructure — Access Token Lifecycle

Implements JWT access token creation, validation, and key management using
PyJWT with HMAC-SHA256 (HS256). Designed for an RS256 migration path per ADR-003.

Public API (for application and middleware layers):
  from app.core.security.jwt.interfaces import JWTService
  from app.core.security.jwt.claims import AccessTokenClaims, DecodedAccessToken
  from app.core.security.jwt.errors import JWTExpiredError, JWTError, ...
  from app.core.security.jwt.dependencies import CurrentJWTService

Internal (infrastructure only):
  service.py     HS256JWTService — concrete implementation
  signing.py     SigningKey, InMemorySigningKeyProvider
"""
