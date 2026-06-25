# tests/orchestrator_tests/test_runtime_refinements.py
import asyncio
from datetime import datetime, timezone, timedelta
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from agents.orchestrator_agent.cache_layer import RuntimeCacheManager, CacheEntry
from agents.orchestrator_agent.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitState
from agents.orchestrator_agent.preflight import PreflightValidator, HealthCheckResult
from agents.orchestrator_agent.service_names import ServiceName

def test_runtime_config_loading():
    env_patch = {
        "GROWTHSCOUT_ENV": "staging",
        "GOOGLE_MAPS_API_KEY": "maps_key_123",
        "GEMINI_API_KEY": "gemini_key_456",
        "SCRAPER_RATE_LIMIT_DELAY": "2.5",
        "FEATURE_FLAGS": "flag_a=true,flag_b=false"
    }
    with patch.dict(os.environ, env_patch):
        config = RuntimeConfig.load_from_env()
        assert config.environment == "staging"
        assert config.google_maps_api_key == "maps_key_123"
        assert config.gemini_api_key == "gemini_key_456"
        assert config.scraper_rate_limit_delay == 2.5
        assert config.feature_flags.get("flag_a") is True
        assert config.feature_flags.get("flag_b") is False
        assert config.config_version == "1.0.0"
        assert config.instance_id.startswith("inst_")

def test_structured_runtime_errors():
    orig_exc = ValueError("Invalid parameter")
    err = GrowthScoutRuntimeError(
        error_code=RuntimeErrorCode.AUTH_ERROR,
        message="Authentication failed",
        service=ServiceName.GEMINI,
        retryable=False,
        correlation_id="corr_xyz",
        original_exception=orig_exc
    )
    
    assert err.error_code == RuntimeErrorCode.AUTH_ERROR
    assert err.service == ServiceName.GEMINI
    assert err.retryable is False
    assert err.correlation_id == "corr_xyz"
    assert err.original_exception == orig_exc
    
    err_dict = err.to_dict()
    assert err_dict["error_code"] == "AUTH_ERROR"
    assert err_dict["service"] == "GEMINI"
    assert err_dict["retryable"] is False
    assert err_dict["correlation_id"] == "corr_xyz"
    assert "Invalid parameter" in err_dict["original_exception"]

def test_cache_layer_operations():
    cache_mgr = RuntimeCacheManager(ttl_discovery=5.0, ttl_audit=10.0)
    
    # Discovery Cache Set / Get / Invalidate
    cache_mgr.discovery.set("HVAC Austin", {"leads": [1, 2]})
    assert cache_mgr.discovery.get("HVAC Austin") == {"leads": [1, 2]}
    
    cache_mgr.invalidate_discovery_cache("HVAC Austin")
    assert cache_mgr.discovery.get("HVAC Austin") is None

    # Audit Cache Set / Get / Clear
    cache_mgr.audit.set("https://example.com", {"score": 90})
    assert cache_mgr.audit.get("https://example.com") == {"score": 90}
    
    cache_mgr.clear_audit_cache()
    assert cache_mgr.audit.get("https://example.com") is None

    # TTL Expiration test
    entry = CacheEntry(value="expired", ttl_seconds=-1.0) # expired in past
    assert entry.is_expired() is True

def test_circuit_breaker_transitions():
    cb = CircuitBreaker(name="test_service", failure_threshold=2, cooldown_seconds=0.1, success_threshold=2)
    
    # 1. Closed state
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True
    
    # 2. Transition Closed -> Open on failures
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    
    # 3. Open state cooldown check
    import time
    time.sleep(0.15)
    
    # Check cooldown expires -> transitions to Half-Open on allow_request
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # 4. Half-Open -> Open on failure
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    
    # Cooldown again
    time.sleep(0.15)
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # 5. Half-Open -> Closed on success threshold met
    cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

@pytest.mark.asyncio
async def test_preflight_validator_crawlers():
    config = RuntimeConfig(
        google_maps_api_key="key",
        gemini_api_key="key"
    )
    validator = PreflightValidator(config)
    
    # Mock create_subprocess_exec to prevent actual spawning
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = MagicMock()
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc
        
        results = await validator.run_checks()
        # Verify that we checked maps, gemini, and servers
        components = [r.component for r in results]
        assert "google_maps_api_key" in components
        assert "gemini_api_key" in components
        assert "local_search_server" in components
        assert "web_analyzer_server" in components
