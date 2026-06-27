# service/infrastructure/config.py
"""
Configuration management for the GrowthScout AI Service Layer.
Uses Pydantic Settings to group configuration categories.

Supports development, staging, and production environment profiles.
Validates required configuration and fails fast on invalid settings.
"""

import os
import sys
import logging
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("growthscout.config")

# Build metadata — populated at container build time or from environment
BUILD_VERSION = os.environ.get("GROWTHSCOUT_BUILD_VERSION", "0.0.0-dev")
BUILD_COMMIT = os.environ.get("GROWTHSCOUT_BUILD_COMMIT", "unknown")
BUILD_TIMESTAMP = os.environ.get("GROWTHSCOUT_BUILD_TIMESTAMP", "unknown")

VALID_ENVIRONMENTS = {"development", "staging", "production"}


class AppConfig(BaseModel):
    name: str = Field(default="growthscout-ai", description="Application name")
    env: str = Field(default="development", description="Environment stage (development, staging, production)")
    debug: bool = Field(default=True, description="Enable debug logging and OpenAPI interactive documentation")
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    log_format: str = Field(default="json", description="Log format: 'json' for structured, 'text' for human-readable")

    @field_validator("env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        if v not in VALID_ENVIRONMENTS:
            raise ValueError(f"Invalid environment '{v}'. Must be one of: {', '.join(sorted(VALID_ENVIRONMENTS))}")
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"Invalid log_level '{v}'. Must be one of: {', '.join(sorted(valid))}")
        return upper


class APIConfig(BaseModel):
    host: str = Field(default="0.0.0.0", description="IP address to bind the service")
    port: int = Field(default=8000, description="Port to expose the FastAPI application")
    prefix: str = Field(default="/api/v1", description="FastAPI prefix for versioned routes")
    max_request_size_bytes: int = Field(default=10_485_760, description="Maximum request body size (10MB default)")


class SecurityConfig(BaseModel):
    api_key_required: bool = Field(default=True, description="Enforce API key header authentication")
    allowed_hosts: List[str] = Field(default_factory=lambda: ["*"], description="CORS allowed host patterns")
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"], description="CORS allowed origins")
    api_keys: List[str] = Field(default_factory=lambda: ["gs_dev_key_12345"], description="Allowed API keys register")
    trusted_hosts: Optional[List[str]] = Field(default=None, description="Trusted host validation list (None = disabled)")
    enable_security_headers: bool = Field(default=True, description="Inject security response headers")


class TelemetryConfig(BaseModel):
    enabled: bool = Field(default=True, description="Enable tracing and metrics compilation")
    service_name: str = Field(default="growthscout-service", description="Service identifier for telemetry spans")


class StorageConfig(BaseModel):
    checkpoint_dir: str = Field(default="artifacts/checkpoints", description="Directory to persist local session state JSONs")


class MCPConfig(BaseModel):
    timeout_seconds: int = Field(default=30, description="Startup and execution timeouts for MCP servers")


class ServiceSettings(BaseSettings):
    """
    Unified settings loader grouping configuration categories.
    Can be overridden via environment variables prefixed with e.g. APP__ENV=production.

    Environment variable examples:
        APP__ENV=production
        APP__DEBUG=false
        APP__LOG_LEVEL=WARNING
        SECURITY__API_KEY_REQUIRED=true
        SECURITY__API_KEYS='["key1","key2"]'
        STORAGE__CHECKPOINT_DIR=/data/checkpoints
    """
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    app: AppConfig = AppConfig()
    api: APIConfig = APIConfig()
    security: SecurityConfig = SecurityConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    storage: StorageConfig = StorageConfig()
    mcp: MCPConfig = MCPConfig()

    @property
    def is_production(self) -> bool:
        """Returns True if running in production environment."""
        return self.app.env == "production"

    @property
    def is_development(self) -> bool:
        """Returns True if running in development environment."""
        return self.app.env == "development"

    def validate_production_requirements(self) -> List[str]:
        """
        Validates that production-required settings are properly configured.
        Returns a list of validation error messages (empty = valid).
        """
        errors = []

        if self.is_production:
            # Debug must be disabled
            if self.app.debug:
                errors.append("APP__DEBUG must be 'false' in production")

            # API key enforcement
            if not self.security.api_key_required:
                errors.append("SECURITY__API_KEY_REQUIRED must be 'true' in production")

            # Default dev key must be removed
            if "gs_dev_key_12345" in self.security.api_keys:
                errors.append("Default development API key must be removed in production")

            # CORS wildcard check
            if "*" in self.security.allowed_origins:
                errors.append("Wildcard CORS origins not allowed in production")

        return errors

    def fail_fast_if_invalid(self) -> None:
        """
        Validates configuration and exits immediately on fatal errors in production.
        Logs warnings in development/staging.
        """
        errors = self.validate_production_requirements()
        if errors:
            for err in errors:
                logger.critical(f"Configuration validation failure: {err}")
            if self.is_production:
                logger.critical("Fatal: Production configuration is invalid. Shutting down.")
                sys.exit(1)
            else:
                for err in errors:
                    logger.warning(f"Non-fatal config warning ({self.app.env}): {err}")


def get_build_info() -> dict:
    """Returns build metadata dictionary."""
    return {
        "version": BUILD_VERSION,
        "commit": BUILD_COMMIT,
        "build_timestamp": BUILD_TIMESTAMP
    }


# Global settings instance
settings = ServiceSettings()
