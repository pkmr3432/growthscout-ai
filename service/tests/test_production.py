# service/tests/test_production.py
"""
Comprehensive test suite for Sprint 7.4 — Production Readiness, Packaging & Deployment.

Tests:
    - Configuration validation (environment, log levels, production requirements)
    - Startup failure cases (invalid environment, invalid log level)
    - Structured JSON logging
    - Security headers middleware
    - Request size limit middleware
    - Enhanced health/readiness/startup endpoints
    - Build metadata exposure
    - Graceful lifecycle ordering
    - Registry initialization state
"""

import json
import logging
import os
import time
import pytest

from fastapi.testclient import TestClient
from service.main import app
from service.infrastructure.config import (
    ServiceSettings, AppConfig, SecurityConfig, APIConfig,
    get_build_info, VALID_ENVIRONMENTS
)
from service.infrastructure.logging import (
    StructuredJSONFormatter, HumanReadableFormatter,
    RequestContextFilter, configure_logging
)
from service.infrastructure.registry import ServiceRegistry
from service.middleware.security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware

AUTH_HEADERS = {"X-API-Key": "gs_dev_key_12345"}
client = TestClient(app)


# ─────────────────────────────────────
# Configuration Validation Tests
# ─────────────────────────────────────

class TestConfigurationValidation:
    """Tests for configuration parsing, validation, and fail-fast behavior."""

    def test_default_settings_are_development(self):
        """Verifies default settings resolve to development environment."""
        settings = ServiceSettings()
        assert settings.app.env == "development"
        assert settings.app.debug is True
        assert settings.is_development is True
        assert settings.is_production is False

    def test_valid_environments(self):
        """Verifies all valid environments are accepted."""
        for env in VALID_ENVIRONMENTS:
            config = AppConfig(env=env)
            assert config.env == env

    def test_invalid_environment_raises(self):
        """Verifies invalid environment values raise validation errors."""
        with pytest.raises(Exception):
            AppConfig(env="invalid_env")

    def test_valid_log_levels(self):
        """Verifies all valid log levels are accepted."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = AppConfig(log_level=level)
            assert config.log_level == level

    def test_invalid_log_level_raises(self):
        """Verifies invalid log levels raise validation errors."""
        with pytest.raises(Exception):
            AppConfig(log_level="VERBOSE")

    def test_log_level_normalized_to_uppercase(self):
        """Verifies log levels are normalized to uppercase."""
        config = AppConfig(log_level="info")
        assert config.log_level == "INFO"

    def test_production_requirements_debug_false(self):
        """Verifies production validation fails when debug is true."""
        settings = ServiceSettings(
            app=AppConfig(env="production", debug=True)
        )
        errors = settings.validate_production_requirements()
        assert any("DEBUG" in e for e in errors)

    def test_production_requirements_api_key_required(self):
        """Verifies production validation fails when API key auth is disabled."""
        settings = ServiceSettings(
            app=AppConfig(env="production", debug=False),
            security=SecurityConfig(api_key_required=False)
        )
        errors = settings.validate_production_requirements()
        assert any("API_KEY_REQUIRED" in e for e in errors)

    def test_production_requirements_default_key_rejected(self):
        """Verifies production validation fails when default dev key is present."""
        settings = ServiceSettings(
            app=AppConfig(env="production", debug=False),
            security=SecurityConfig(api_keys=["gs_dev_key_12345"])
        )
        errors = settings.validate_production_requirements()
        assert any("development API key" in e for e in errors)

    def test_production_requirements_cors_wildcard_rejected(self):
        """Verifies production validation fails with wildcard CORS origins."""
        settings = ServiceSettings(
            app=AppConfig(env="production", debug=False),
            security=SecurityConfig(
                api_keys=["prod_key_abc"],
                allowed_origins=["*"]
            )
        )
        errors = settings.validate_production_requirements()
        assert any("Wildcard CORS" in e for e in errors)

    def test_development_passes_validation(self):
        """Verifies development environment passes validation (warnings only)."""
        settings = ServiceSettings()
        errors = settings.validate_production_requirements()
        # In development, validation returns empty (no prod requirements)
        assert len(errors) == 0

    def test_is_production_property(self):
        """Verifies is_production property behavior."""
        prod = ServiceSettings(app=AppConfig(env="production"))
        dev = ServiceSettings(app=AppConfig(env="development"))
        assert prod.is_production is True
        assert dev.is_production is False

    def test_max_request_size_default(self):
        """Verifies default max request size is 10MB."""
        config = APIConfig()
        assert config.max_request_size_bytes == 10_485_760


# ─────────────────────────────────────
# Build Metadata Tests
# ─────────────────────────────────────

class TestBuildMetadata:
    """Tests for build version metadata exposure."""

    def test_build_info_structure(self):
        """Verifies build info returns expected keys."""
        info = get_build_info()
        assert "version" in info
        assert "commit" in info
        assert "build_timestamp" in info

    def test_health_includes_version(self):
        """Verifies /health response includes version metadata."""
        response = client.get("/health")
        data = response.json()
        assert "version" in data

    def test_startup_check_includes_build_info(self):
        """Verifies /startup-check includes build metadata."""
        response = client.get("/startup-check")
        data = response.json()
        assert "version" in data
        assert "commit" in data
        assert "build_timestamp" in data
        assert "environment" in data
        assert "uptime_seconds" in data

    def test_ready_includes_environment(self):
        """Verifies /ready includes environment and version."""
        response = client.get("/ready")
        data = response.json()
        assert "environment" in data
        assert "version" in data


# ─────────────────────────────────────
# Structured Logging Tests
# ─────────────────────────────────────

class TestStructuredLogging:
    """Tests for the structured JSON logging infrastructure."""

    def test_json_formatter_produces_valid_json(self):
        """Verifies StructuredJSONFormatter outputs parseable JSON."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="growthscout.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test log message",
            args=None,
            exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["component"] == "growthscout.test"
        assert parsed["message"] == "Test log message"
        assert "timestamp" in parsed

    def test_json_formatter_includes_exception(self):
        """Verifies exception information is included in JSON output."""
        formatter = StructuredJSONFormatter()
        try:
            raise ValueError("test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="growthscout.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=99,
            msg="Error occurred",
            args=None,
            exc_info=exc_info
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "test exception" in parsed["exception"]["message"]

    def test_json_formatter_strips_none_values(self):
        """Verifies None values are stripped from JSON output."""
        formatter = StructuredJSONFormatter()
        record = logging.LogRecord(
            name="growthscout.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Clean log",
            args=None,
            exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        # request_id should not be present when None
        assert "request_id" not in parsed

    def test_request_context_filter_injects_fields(self):
        """Verifies RequestContextFilter injects context into log records."""
        RequestContextFilter.set_context(
            request_id="req_123",
            correlation_id="corr_456",
            session_id="sess_789"
        )
        ctx_filter = RequestContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="", args=None, exc_info=None
        )
        ctx_filter.filter(record)
        assert record.request_id == "req_123"
        assert record.correlation_id == "corr_456"
        assert record.session_id == "sess_789"
        RequestContextFilter.clear_context()

    def test_request_context_filter_clear(self):
        """Verifies RequestContextFilter.clear_context removes fields."""
        RequestContextFilter.set_context(request_id="req_abc")
        RequestContextFilter.clear_context()
        ctx_filter = RequestContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="", lineno=0, msg="", args=None, exc_info=None
        )
        ctx_filter.filter(record)
        assert record.request_id is None

    def test_human_readable_formatter(self):
        """Verifies HumanReadableFormatter produces human-readable output."""
        formatter = HumanReadableFormatter()
        record = logging.LogRecord(
            name="growthscout.test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Human readable log",
            args=None,
            exc_info=None
        )
        output = formatter.format(record)
        assert "Human readable log" in output
        assert "INFO" in output


# ─────────────────────────────────────
# Security Headers Tests
# ─────────────────────────────────────

class TestSecurityHeaders:
    """Tests for security response headers."""

    def test_x_content_type_options_header(self):
        """Verifies X-Content-Type-Options: nosniff is set."""
        response = client.get("/health")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_x_frame_options_header(self):
        """Verifies X-Frame-Options: DENY is set."""
        response = client.get("/health")
        assert response.headers.get("x-frame-options") == "DENY"

    def test_x_xss_protection_header(self):
        """Verifies X-XSS-Protection is set."""
        response = client.get("/health")
        assert response.headers.get("x-xss-protection") == "1; mode=block"

    def test_referrer_policy_header(self):
        """Verifies Referrer-Policy header is set."""
        response = client.get("/health")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy_header(self):
        """Verifies Permissions-Policy header is set."""
        response = client.get("/health")
        assert "camera=()" in response.headers.get("permissions-policy", "")

    def test_security_headers_on_api_endpoints(self):
        """Verifies security headers are present on API endpoints."""
        response = client.post(
            "/api/v1/sessions",
            json={"niche": "test", "location": "test", "max_leads": 1},
            headers=AUTH_HEADERS
        )
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"


# ─────────────────────────────────────
# Request Size Limit Tests
# ─────────────────────────────────────

class TestRequestSizeLimit:
    """Tests for request body size limit middleware."""

    def test_normal_request_passes(self):
        """Verifies normal-sized requests pass through."""
        response = client.post(
            "/api/v1/sessions",
            json={"niche": "normal", "location": "Test, US", "max_leads": 5},
            headers=AUTH_HEADERS
        )
        assert response.status_code == 201

    def test_oversized_request_rejected(self):
        """Verifies oversized Content-Length is rejected with 413."""
        response = client.post(
            "/api/v1/sessions",
            json={"niche": "test"},
            headers={**AUTH_HEADERS, "Content-Length": "999999999"}
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


# ─────────────────────────────────────
# Enhanced Health Probe Tests
# ─────────────────────────────────────

class TestEnhancedHealthProbes:
    """Tests for enhanced health, readiness, and startup endpoints."""

    def test_health_includes_uptime(self):
        """Verifies /health includes uptime_seconds."""
        response = client.get("/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0

    def test_readiness_includes_checks(self):
        """Verifies /ready includes structured check results."""
        response = client.get("/ready")
        data = response.json()
        assert data["status"] in ["READY", "DEGRADED"]
        assert "checks" in data
        assert "checkpoint_storage" in data["checks"]

    def test_readiness_checks_service_registry(self):
        """Verifies /ready checks service registry."""
        response = client.get("/ready")
        data = response.json()
        assert data["checks"]["service_registry"] == "ok"

    def test_readiness_checks_event_publisher(self):
        """Verifies /ready checks event publisher."""
        response = client.get("/ready")
        data = response.json()
        assert data["checks"]["event_publisher"] == "ok"

    def test_startup_check_includes_environment(self):
        """Verifies /startup-check includes deployment environment."""
        response = client.get("/startup-check")
        data = response.json()
        assert "environment" in data
        assert data["environment"] in VALID_ENVIRONMENTS

    def test_startup_check_includes_debug_mode(self):
        """Verifies /startup-check includes debug flag."""
        response = client.get("/startup-check")
        data = response.json()
        assert "debug" in data
        assert isinstance(data["debug"], bool)


# ─────────────────────────────────────
# Registry Lifecycle Tests
# ─────────────────────────────────────

class TestRegistryLifecycle:
    """Tests for ServiceRegistry initialization and shutdown ordering."""

    @pytest.mark.anyio
    async def test_registry_initialization(self):
        """Verifies registry initializes without errors."""
        reg = ServiceRegistry()
        await reg.initialize()
        assert reg.is_initialized is True
        await reg.shutdown()
        assert reg.is_initialized is False

    @pytest.mark.anyio
    async def test_registry_uptime_tracking(self):
        """Verifies registry tracks uptime."""
        reg = ServiceRegistry()
        assert reg.uptime_seconds >= 0
        await reg.initialize()
        assert reg.uptime_seconds > 0
        await reg.shutdown()

    @pytest.mark.anyio
    async def test_registry_shutdown_idempotent(self):
        """Verifies registry shutdown is idempotent (can be called multiple times)."""
        reg = ServiceRegistry()
        await reg.initialize()
        await reg.shutdown()
        await reg.shutdown()  # Second shutdown should not raise
        assert reg.is_initialized is False

    def test_registry_components_initialized(self):
        """Verifies registry creates all required components."""
        reg = ServiceRegistry()
        assert reg.lock_manager is not None
        assert reg.task_scheduler is not None
        assert reg.checkpoint_store is not None
        assert reg.event_publisher is not None
        assert reg.authenticator is not None


# ─────────────────────────────────────
# Middleware Stack Integration Tests
# ─────────────────────────────────────

class TestMiddlewareStack:
    """Tests for the complete middleware stack integration."""

    def test_telemetry_headers_present(self):
        """Verifies telemetry headers are set on responses."""
        response = client.get("/health")
        assert "x-request-id" in response.headers
        assert "x-correlation-id" in response.headers
        assert "x-process-time" in response.headers

    def test_custom_request_id_propagated(self):
        """Verifies custom X-Request-ID is propagated through."""
        custom_id = "custom-req-12345"
        response = client.get("/health", headers={"X-Request-ID": custom_id})
        assert response.headers["x-request-id"] == custom_id

    def test_custom_correlation_id_propagated(self):
        """Verifies custom X-Correlation-ID is propagated through."""
        response = client.get("/health", headers={"X-Correlation-ID": "corr-test"})
        assert response.headers["x-correlation-id"] == "corr-test"

    def test_process_time_is_positive(self):
        """Verifies X-Process-Time header contains a valid duration."""
        response = client.get("/health")
        process_time = response.headers["x-process-time"]
        assert process_time.endswith("s")
        duration = float(process_time.rstrip("s"))
        assert duration >= 0.0


# ─────────────────────────────────────
# Docker Build Validation Tests
# ─────────────────────────────────────

class TestDockerBuildValidation:
    """Tests validating Docker build artifacts exist and are well-formed."""

    def test_dockerfile_exists(self):
        """Verifies Dockerfile exists in project root."""
        assert os.path.isfile(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Dockerfile"
        ))

    def test_dockerignore_exists(self):
        """Verifies .dockerignore exists in project root."""
        assert os.path.isfile(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            ".dockerignore"
        ))

    def test_requirements_txt_exists(self):
        """Verifies requirements.txt exists for Docker builds."""
        assert os.path.isfile(os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "requirements.txt"
        ))

    def test_dockerfile_references_nonroot_user(self):
        """Verifies Dockerfile creates and uses a non-root user."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Dockerfile"
        )
        with open(dockerfile_path) as f:
            content = f.read()
        assert "growthscout" in content
        assert "USER growthscout" in content

    def test_dockerfile_has_healthcheck(self):
        """Verifies Dockerfile includes HEALTHCHECK instruction."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Dockerfile"
        )
        with open(dockerfile_path) as f:
            content = f.read()
        assert "HEALTHCHECK" in content

    def test_dockerfile_multistage_build(self):
        """Verifies Dockerfile uses multi-stage build."""
        dockerfile_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "Dockerfile"
        )
        with open(dockerfile_path) as f:
            content = f.read()
        assert content.count("FROM ") >= 2  # At least 2 stages


# ─────────────────────────────────────
# Documentation Existence Tests
# ─────────────────────────────────────

class TestDeploymentDocumentation:
    """Tests verifying deployment documentation exists."""

    def test_deployment_guide_exists(self):
        """Verifies deployment_guide.md exists."""
        service_dir = os.path.dirname(os.path.dirname(__file__))
        assert os.path.isfile(os.path.join(service_dir, "deployment_guide.md"))

    def test_operations_runbook_exists(self):
        """Verifies operations_runbook.md exists."""
        service_dir = os.path.dirname(os.path.dirname(__file__))
        assert os.path.isfile(os.path.join(service_dir, "operations_runbook.md"))

    def test_service_contract_exists(self):
        """Verifies SERVICE_CONTRACT.md exists."""
        service_dir = os.path.dirname(os.path.dirname(__file__))
        assert os.path.isfile(os.path.join(service_dir, "SERVICE_CONTRACT.md"))
