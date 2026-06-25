# tests/orchestrator_tests/test_runtime_polish.py
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from agents.orchestrator_agent.cache_layer import RuntimeCacheManager
from agents.orchestrator_agent.circuit_breaker import CircuitBreakerRegistry
from agents.orchestrator_agent.preflight import PreflightValidator, HealthCategory, HealthCheckResult
from agents.orchestrator_agent.service_names import ServiceName
from agents.orchestrator_agent.protocols import SystemClock, FrozenClock, ClockProtocol
from agents.orchestrator_agent.runtime_services import RuntimeServices
from agents.orchestrator_agent.workflow_executor import WorkflowExecutor, TransitionPlan
from agents.orchestrator_agent.state_machine.workflow_context import WorkflowContext, WorkflowTimestamps, ExecutionMetadata
from agents.orchestrator_agent.state_machine.states import WorkflowState
from agents.orchestrator_agent.agent import GrowthScoutOrchestrator, OrchestratorDependencies

def test_service_name_enum():
    assert ServiceName.GOOGLE_MAPS == "GOOGLE_MAPS"
    assert ServiceName.GEMINI == "GEMINI"
    assert ServiceName.WEBSITE_SCRAPER == "WEBSITE_SCRAPER"
    assert ServiceName.LOCAL_SEARCH_MCP == "LOCAL_SEARCH_MCP"
    assert ServiceName.WEB_ANALYZER_MCP == "WEB_ANALYZER_MCP"

def test_health_category_enum():
    assert HealthCategory.CONFIGURATION == "CONFIGURATION"
    assert HealthCategory.AUTHENTICATION == "AUTHENTICATION"
    assert HealthCategory.CONNECTIVITY == "CONNECTIVITY"
    assert HealthCategory.DEPENDENCIES == "DEPENDENCIES"
    assert HealthCategory.RUNTIME == "RUNTIME"
    assert HealthCategory.EXTERNAL_SERVICES == "EXTERNAL_SERVICES"

def test_clock_implementations():
    sys_clock = SystemClock()
    assert isinstance(sys_clock, ClockProtocol)
    t1 = sys_clock.now_utc()
    assert isinstance(t1, datetime)
    assert t1.tzinfo == timezone.utc

    fixed_time = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
    frozen_clock = FrozenClock(fixed_time)
    assert isinstance(frozen_clock, ClockProtocol)
    assert frozen_clock.now_utc() == fixed_time

    new_fixed = fixed_time + timedelta(hours=1)
    frozen_clock.set_time(new_fixed)
    assert frozen_clock.now_utc() == new_fixed

def test_runtime_services_container():
    cfg = RuntimeConfig()
    cache_mgr = RuntimeCacheManager()
    metrics = MagicMock()
    cb = MagicMock()
    fp = MagicMock()
    clock = SystemClock()
    ep = MagicMock()
    aw = MagicMock()
    ci = MagicMock()
    wr = MagicMock()
    preflight = MagicMock()

    services = RuntimeServices(
        config=cfg,
        cache_manager=cache_mgr,
        metrics_collector=metrics,
        cb_registry=cb,
        failure_policy=fp,
        clock=clock,
        event_publisher=ep,
        audit_writer=aw,
        checkpoint_interface=ci,
        worker_registry=wr,
        preflight_validator=preflight
    )

    assert services.config is cfg
    assert services.cache_manager is cache_mgr
    assert services.clock is clock

def test_cache_statistics_gathering():
    cache_mgr = RuntimeCacheManager(ttl_discovery=60.0, ttl_audit=60.0)
    
    # Check initial counters
    assert cache_mgr.hits == 0
    assert cache_mgr.misses == 0
    assert cache_mgr.evictions == 0
    assert cache_mgr.expired_entries == 0

    # Miss (queries discovery then audit, causing 2 misses total)
    assert cache_mgr.get("nonexistent") is None
    assert cache_mgr.misses == 2

    # Set and Hit
    cache_mgr.set("key1", "val1")
    assert cache_mgr.get("key1") == "val1"
    assert cache_mgr.hits == 1

    # Eviction on overwrite
    cache_mgr.set("key1", "val2")
    assert cache_mgr.evictions == 1

@pytest.mark.asyncio
async def test_preflight_version_checking():
    # Setup incompatible config
    cfg = RuntimeConfig(
        google_maps_api_key="key",
        gemini_api_key="key",
        config_version="0.9.0",
        minimum_supported_version="1.0.0"
    )

    validator = PreflightValidator(cfg)
    with pytest.raises(GrowthScoutRuntimeError) as exc_info:
        await validator.run_checks()
    assert exc_info.value.error_code == RuntimeErrorCode.CONFIGURATION_ERROR
    assert "Incompatible config version" in exc_info.value.message

    # Setup invalid version format
    cfg_invalid = RuntimeConfig(
        google_maps_api_key="key",
        gemini_api_key="key",
        config_version="invalid_version"
    )
    validator_invalid = PreflightValidator(cfg_invalid)
    with pytest.raises(GrowthScoutRuntimeError) as exc_info:
        await validator_invalid.run_checks()
    assert exc_info.value.error_code == RuntimeErrorCode.CONFIGURATION_ERROR
    assert "Invalid version format" in exc_info.value.message

@pytest.mark.asyncio
async def test_workflow_lifecycle_hooks():
    deps = OrchestratorDependencies()
    deps.worker_registry = MagicMock()
    deps.worker_registry.get.return_value = MagicMock()

    # Create frozen clock
    fixed_time = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)
    clock = FrozenClock(fixed_time)

    services = RuntimeServices(
        config=RuntimeConfig(),
        cache_manager=RuntimeCacheManager(),
        metrics_collector=deps.metrics_collector,
        cb_registry=deps.failure_policy.cb_registry,
        failure_policy=deps.failure_policy,
        clock=clock,
        event_publisher=deps.event_publisher,
        audit_writer=deps.audit_writer,
        checkpoint_interface=deps.checkpoint_interface,
        worker_registry=deps.worker_registry,
        preflight_validator=MagicMock()
    )

    executor = WorkflowExecutor(
        services=services,
        tc=deps.transition_controller,
        mg=deps.memory_governor,
        ev=deps.evidence_validator,
        rc=deps.resumability_controller
    )

    before_wf_called = []
    after_wf_called = []
    before_state_called = []
    after_state_called = []
    before_transition_called = []
    after_transition_called = []

    executor.before_workflow_hooks.append(lambda ctx: before_wf_called.append(ctx))
    executor.after_workflow_hooks.append(lambda ctx: after_wf_called.append(ctx))
    executor.before_state_hooks.append(lambda ctx: before_state_called.append(ctx))
    executor.after_state_hooks.append(lambda ctx: after_state_called.append(ctx))
    executor.before_transition_hooks.append(lambda ctx, plan: before_transition_called.append((ctx, plan)))
    executor.after_transition_hooks.append(lambda ctx, new_ctx: after_transition_called.append((ctx, new_ctx)))

    # Minimal WorkflowContext for testing IDLE -> DISCOVERING
    context = WorkflowContext(
        session_id="sess_12345678",
        workflow_id="wf_12345678",
        current_state=WorkflowState.IDLE,
        workflow_metadata={"niche": "plumbing", "location": "Austin", "max_leads": 5},
        timestamps=WorkflowTimestamps(
            created_at=fixed_time,
            updated_at=fixed_time,
            state_entered_at=fixed_time
        ),
        execution_metadata=ExecutionMetadata(
            correlation_id="corr_hooks",
            trigger_source="API"
        )
    )

    # Let's execute single step IDLE -> DISCOVERING
    new_ctx = await executor.execute_step(context)

    assert len(before_state_called) == 1
    assert before_state_called[0].current_state == WorkflowState.IDLE
    assert len(after_state_called) == 1
    assert after_state_called[0].current_state == WorkflowState.DISCOVERING
    assert len(before_transition_called) == 1
    assert before_transition_called[0][1].target_state == WorkflowState.DISCOVERING
    assert len(after_transition_called) == 1
    assert after_transition_called[0][1].current_state == WorkflowState.DISCOVERING
