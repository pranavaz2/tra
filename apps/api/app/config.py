"""
Travix AI — Application Configuration

Single source of truth for all environment-driven configuration.
All settings are loaded from environment variables (or .env in local dev).

Usage:
    from app.config import get_settings
    settings = get_settings()

Rules:
    - Never import os.environ directly in application code — use this module.
    - SecretStr fields render as '**********' in logs and repr.
    - get_settings() is cached; clear the cache in tests via get_settings.cache_clear().
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Field naming mirrors the environment variable name exactly (case-insensitive).
    Sensitive fields use SecretStr to prevent accidental logging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = "Travix AI"
    app_version: str = "0.1.0"
    app_env: Literal["local", "test", "ci", "staging", "production"] = "local"
    app_debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    # -------------------------------------------------------------------------
    # Security
    # -------------------------------------------------------------------------
    secret_key: SecretStr
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8085",
        "http://localhost:8081",
        "http://127.0.0.1:8085",
        "http://127.0.0.1:8000",
        "http://10.52.14.15:8085",
        "http://10.52.14.15:8000",
    ]
    cors_allowed_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    cors_allowed_headers: list[str] = ["Authorization", "Content-Type", "Accept", "X-Request-ID"]

    # -------------------------------------------------------------------------
    # JWT (see ADR-003: HS256 with RS256 migration path)
    # -------------------------------------------------------------------------
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    jwt_issuer: str = "https://api.travix.ai"
    jwt_audience: str = "travix-mobile"
    jwt_leeway_seconds: int = 30  # Clock skew tolerance; 0 in tests
    jwt_key_id: str = "default-v1"  # kid header value; change to rotate keys

    # -------------------------------------------------------------------------
    # Argon2id — password hashing (see ADR-004)
    # OWASP-compliant defaults: 64 MiB memory, 3 iterations, 4 lanes.
    # Increase argon2_time_cost or argon2_memory_cost as hardware improves.
    # -------------------------------------------------------------------------
    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536  # 64 MiB in KiB
    argon2_parallelism: int = 4
    argon2_hash_len: int = 32  # 256-bit output
    argon2_salt_len: int = 16  # 128-bit salt

    # -------------------------------------------------------------------------
    # Database — PostgreSQL + PostGIS
    # -------------------------------------------------------------------------
    database_url: SecretStr
    database_sync_url: SecretStr
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_pool_pre_ping: bool = True
    db_slow_query_threshold_ms: float = 200.0

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379"
    redis_cache_db: int = 0
    redis_task_queue_db: int = 1
    redis_token_revocation_db: int = 2
    redis_rate_limit_db: int = 3
    redis_ai_cache_db: int = 4
    redis_session_db: int = 5
    redis_default_ttl: int = 300

    # -------------------------------------------------------------------------
    # AI Provider
    # -------------------------------------------------------------------------
    ai_provider: Literal["openai", "anthropic", "gemini", "mock"] = "mock"
    ai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    ai_model: str = "gemini-3.6-flash"
    ai_temperature: float = 0.4
    ai_max_tokens: int = 4096
    ai_timeout_seconds: int = 120
    ai_max_retries: int = 3

    # -------------------------------------------------------------------------
    # Maps & Places Provider
    # -------------------------------------------------------------------------
    maps_provider: Literal["google", "osm", "mock"] = "mock"
    places_provider: Literal["google", "osm", "mock"] = "mock"
    google_maps_server_api_key: SecretStr | None = None
    google_places_api_key: SecretStr | None = None
    google_maps_client_api_key: SecretStr | None = None

    # -------------------------------------------------------------------------
    # Weather — Open-Meteo (free tier, no key required)
    # -------------------------------------------------------------------------
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"
    weather_cache_ttl: int = 1800

    # -------------------------------------------------------------------------
    # Email — Resend (future)
    # -------------------------------------------------------------------------
    email_provider: Literal["resend", "mock"] = "mock"
    resend_api_key: SecretStr | None = None
    email_from_address: str = "noreply@travixai.com"
    email_from_name: str = "Travix AI"

    # -------------------------------------------------------------------------
    # Storage — Cloudflare R2 (future)
    # -------------------------------------------------------------------------
    storage_provider: Literal["r2", "s3", "mock"] = "mock"
    r2_account_id: str | None = None
    r2_access_key_id: SecretStr | None = None
    r2_secret_access_key: SecretStr | None = None
    r2_bucket_name: str = "travix-ai-assets"
    r2_public_url: str | None = None
    storage_max_file_size: int = 10_485_760  # 10 MB

    # -------------------------------------------------------------------------
    # Notifications — Firebase Cloud Messaging (future)
    # -------------------------------------------------------------------------
    notification_provider: Literal["fcm", "mock"] = "mock"
    firebase_service_account_path: str | None = None
    firebase_project_id: str | None = None

    # -------------------------------------------------------------------------
    # ARQ — Async task queue
    # -------------------------------------------------------------------------
    arq_worker_concurrency: int = 10
    arq_max_retries: int = 3
    arq_job_timeout: int = 90

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "text"] = "json"

    # -------------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------------
    registration_auto_verify_email: bool = False
    """
    When True, newly registered users are immediately marked as email-verified
    without going through the email verification flow.

    MUST be False in production. Intended for local development and CI only.
    Driven by environment variable REGISTRATION_AUTO_VERIFY_EMAIL=true.
    Never set this from code — always from the environment / .env file.
    """
    registration_require_email_verification: bool = True
    """
    When True (production default), users must verify their email address
    before they can log in. Set to False only for internal / B2B deployments
    where email verification is handled by an SSO provider.
    """

    # -------------------------------------------------------------------------
    # Rate limiting
    # -------------------------------------------------------------------------
    rate_limit_public_rpm: int = 60
    rate_limit_auth_rpm: int = 120
    rate_limit_ai_rpm: int = 10

    # -------------------------------------------------------------------------
    # Monitoring — Sentry
    # -------------------------------------------------------------------------
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.0

    # =========================================================================
    # Computed properties
    # =========================================================================

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_test(self) -> bool:
        return self.app_env in ("test", "ci")

    @property
    def show_docs(self) -> bool:
        """Expose Swagger/ReDoc only in non-production environments."""
        return not self.is_production

    # =========================================================================
    # Cross-field validation
    # =========================================================================

    @model_validator(mode="after")
    def validate_provider_credentials(self) -> Settings:
        effective_ai_key = self.ai_api_key or self.gemini_api_key
        if self.ai_provider != "mock" and not effective_ai_key:
            raise ValueError(
                f"AI_API_KEY (or GEMINI_API_KEY) is required when AI_PROVIDER is '{self.ai_provider}'"
            )
        effective_places_key = (
            self.google_places_api_key or self.google_maps_server_api_key
        )
        effective_places_key_value = (
            effective_places_key.get_secret_value() if effective_places_key else None
        )
        if (
            self.maps_provider == "google" or self.places_provider == "google"
        ) and not effective_places_key_value:
            raise ValueError(
                "GOOGLE_MAPS_SERVER_API_KEY (or GOOGLE_PLACES_API_KEY) is required when PLACES_PROVIDER is 'google'"
            )
        if self.is_production and self.app_debug:
            raise ValueError("APP_DEBUG must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings instance.

    The cache is populated on first call and reused for the lifetime of the
    process. In tests, call get_settings.cache_clear() before overriding
    environment variables.
    """
    return Settings()
