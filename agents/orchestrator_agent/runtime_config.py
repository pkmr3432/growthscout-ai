# agents/orchestrator_agent/runtime_config.py
from datetime import datetime, timezone
import os
from typing import Dict, Literal, Optional
import uuid
from pydantic import BaseModel, Field

class RuntimeConfig(BaseModel):
    # Immutable runtime metadata
    config_version: str = "1.0.0"
    schema_version: str = "1.0.0"
    minimum_supported_version: str = "1.0.0"
    environment: Literal["development", "staging", "production"] = "development"
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    instance_id: str = Field(default_factory=lambda: f"inst_{uuid.uuid4().hex[:8]}")

    # API credentials
    google_maps_api_key: str = ""
    gemini_api_key: str = ""
    google_application_credentials: Optional[str] = None

    # Scraper config
    scraper_user_agent: str = "GrowthScoutBot/1.0"
    scraper_rate_limit_delay: float = 1.0

    # HTTP & Retries
    http_timeout_seconds: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 2.0

    # Cache TTLs
    cache_ttl_discovery: float = 3600.0
    cache_ttl_audit: float = 86400.0

    # Circuit Breakers
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_cooldown_seconds: float = 60.0
    circuit_breaker_success_threshold: int = 1

    # Feature flags
    feature_flags: Dict[str, bool] = Field(default_factory=dict)

    model_config = {
        "frozen": True
    }

    @classmethod
    def load_from_env(cls) -> "RuntimeConfig":
        env_val = os.environ.get("GROWTHSCOUT_ENV", "development").lower()
        env: Literal["development", "staging", "production"] = "development"
        if env_val in ["development", "staging", "production"]:
            env = env_val  # type: ignore

        maps_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
        gemini_key = os.environ.get("GEMINI_API_KEY", "")
        g_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", None)
        user_agent = os.environ.get("SCRAPER_USER_AGENT", "GrowthScoutBot/1.0")

        try:
            rate_limit_delay = float(os.environ.get("SCRAPER_RATE_LIMIT_DELAY", "1.0"))
        except ValueError:
            rate_limit_delay = 1.0

        try:
            timeout = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "30.0"))
        except ValueError:
            timeout = 30.0

        try:
            retries = int(os.environ.get("MAX_RETRIES", "3"))
        except ValueError:
            retries = 3

        try:
            backoff = float(os.environ.get("BACKOFF_FACTOR", "2.0"))
        except ValueError:
            backoff = 2.0

        try:
            ttl_discovery = float(os.environ.get("CACHE_TTL_DISCOVERY", "3600.0"))
        except ValueError:
            ttl_discovery = 3600.0

        try:
            ttl_audit = float(os.environ.get("CACHE_TTL_AUDIT", "86400.0"))
        except ValueError:
            ttl_audit = 86400.0

        try:
            cb_threshold = int(os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3"))
        except ValueError:
            cb_threshold = 3

        try:
            cb_cooldown = float(os.environ.get("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "60.0"))
        except ValueError:
            cb_cooldown = 60.0

        try:
            cb_success = int(os.environ.get("CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "1"))
        except ValueError:
            cb_success = 1

        ff_str = os.environ.get("FEATURE_FLAGS", "")
        ff = {}
        if ff_str:
            for pair in ff_str.split(","):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    ff[k.strip()] = v.strip().lower() in ["true", "1", "yes"]

        return cls(
            config_version="1.0.0",
            environment=env,
            google_maps_api_key=maps_key,
            gemini_api_key=gemini_key,
            google_application_credentials=g_creds,
            scraper_user_agent=user_agent,
            scraper_rate_limit_delay=rate_limit_delay,
            http_timeout_seconds=timeout,
            max_retries=retries,
            backoff_factor=backoff,
            cache_ttl_discovery=ttl_discovery,
            cache_ttl_audit=ttl_audit,
            circuit_breaker_failure_threshold=cb_threshold,
            circuit_breaker_cooldown_seconds=cb_cooldown,
            circuit_breaker_success_threshold=cb_success,
            feature_flags=ff,
        )
