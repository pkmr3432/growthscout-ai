# tests/orchestrator_tests/test_live_runtime_polish.py
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from agents.orchestrator_agent.interfaces.worker_invocation import (
    WorkerRegistry,
    WorkerInvocationRequest,
    WorkerInvocationResult,
    WorkerExecutionResult,
)
from agents.orchestrator_agent.run_budget import WorkflowRunBudget
from agents.orchestrator_agent.exceptions import CostThresholdExceededError
from agents.orchestrator_agent.error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from agents.orchestrator_agent.workflow_executor import WorkflowExecutor
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    ExecutionMetadata,
    WorkflowMetadata,
    WorkflowTimestamps,
)
from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.shared.schemas import DiscoveryLeadsSchema

def test_worker_registry_lazy_factory():
    """Verify registry registers and instantiates via custom factory callables."""
    registry = WorkerRegistry()
    
    # Register custom dummy agent factory
    dummy_agent = MagicMock()
    dummy_agent.name = "dummy_agent"
    
    factory_called = 0
    def dummy_factory():
        nonlocal factory_called
        factory_called += 1
        return dummy_agent
        
    registry.register("dummy_worker", dummy_factory)
    
    # Should not be instantiated until first get()
    assert factory_called == 0
    
    # First get resolves and caches
    resolved = registry.get("dummy_worker")
    assert resolved is dummy_agent
    assert factory_called == 1
    
    # Second get returns from cache without calling factory again
    resolved_cached = registry.get("dummy_worker")
    assert resolved_cached is dummy_agent
    assert factory_called == 1

def test_workflow_run_budget_enforcement():
    """Verify that can_continue and cost tracking enforce limits."""
    budget = WorkflowRunBudget(
        max_gemini_requests=2,
        max_maps_requests=1,
        max_pages_crawled=1,
        max_cost_limit=0.010, # $0.01
        gemini_cost_per_request=0.002,
        maps_cost_per_request=0.005,
        pages_cost_per_request=0.001
    )
    
    # Verify initial checks
    assert budget.can_continue("gemini") is True
    assert budget.can_continue("maps") is True
    assert budget.can_continue("scraper") is True
    
    # Record maps request
    budget.record_operation("maps")
    assert budget.maps_requests == 1
    assert budget.estimated_cost == pytest.approx(0.005)
    # Maps budget exceeded
    assert budget.can_continue("maps") is False
    
    # Gemini and scraper still allowed
    assert budget.can_continue("gemini") is True
    assert budget.can_continue("scraper") is True
    
    # Record Gemini
    budget.record_operation("gemini")
    assert budget.gemini_requests == 1
    assert budget.estimated_cost == pytest.approx(0.007) # 0.005 + 0.002
    
    # Record another Gemini
    budget.record_operation("gemini")
    assert budget.gemini_requests == 2
    assert budget.estimated_cost == pytest.approx(0.009)
    
    # Gemini requests limit reached
    assert budget.can_continue("gemini") is False
    
    # Record scraper
    budget.record_operation("scraper")
    assert budget.pages_crawled == 1
    assert budget.estimated_cost == pytest.approx(0.010)
    
    # Total cost limit reached
    assert budget.can_continue("scraper") is False

def test_worker_execution_result_serialization():
    """Verify WorkerExecutionResult structure and serialization."""
    result = WorkerExecutionResult(
        success=True,
        worker_name="business_discovery_agent",
        output=None,
        metrics={"gemini_requests": 3, "estimated_cost": 0.006},
        evidence=[{"lead_name": "Test Lead"}],
        runtime=1.5,
        retries=1,
        warnings=["Rate limit close"],
        correlation_id="corr-12345"
    )
    
    assert result.success is True
    assert result.runtime == 1.5
    assert result.retries == 1
    assert result.correlation_id == "corr-12345"
    
    # JSON round trip via pydantic serialization
    dumped = result.model_dump(mode="json")
    assert dumped["success"] is True
    assert dumped["worker_name"] == "business_discovery_agent"
    assert dumped["metrics"]["gemini_requests"] == 3
    assert dumped["evidence"][0]["lead_name"] == "Test Lead"
    assert dumped["runtime"] == 1.5

@pytest.mark.asyncio
async def test_workflow_timeline_recording_and_budget_exceeded():
    """Verify timeline recording and budget exceeded error handling in executor."""
    config = RuntimeConfig(
        max_gemini_requests=0,  # Force budget breach immediately
        gemini_api_key="test_key"
    )
    
    # Create a minimal executor
    from agents.orchestrator_agent.runtime_services import RuntimeServices
    from agents.orchestrator_agent.protocols import SystemClock
    from agents.orchestrator_agent.metrics_collector import InMemoryMetricsCollector
    from agents.orchestrator_agent.interfaces.events import StdoutEventPublisher
    from agents.orchestrator_agent.hooks.audit_trail import AuditTrailWriter
    from agents.orchestrator_agent.circuit_breaker import CircuitBreakerRegistry
    from agents.orchestrator_agent.failure_policy import FailurePolicy
    from agents.orchestrator_agent.cache_layer import RuntimeCacheManager
    
    cbr = CircuitBreakerRegistry()
    services = RuntimeServices(
        config=config,
        cache_manager=RuntimeCacheManager(),
        metrics_collector=InMemoryMetricsCollector(),
        cb_registry=cbr,
        failure_policy=FailurePolicy(config=config, cb_registry=cbr),
        clock=SystemClock(),
        event_publisher=StdoutEventPublisher(),
        audit_writer=AuditTrailWriter(),
        checkpoint_interface=MagicMock(),
        worker_registry=WorkerRegistry(),
        preflight_validator=MagicMock(),
    )
    
    executor = WorkflowExecutor(services=services)
    
    # Mock WorkerRegistry to return dummy LlmAgent
    dummy_agent = MagicMock()
    dummy_agent.name = "dummy_agent"
    executor._wr.get = MagicMock(return_value=dummy_agent)
    
    # Create simple request
    now = datetime.now(timezone.utc)
    context = WorkflowContext(
        session_id="sess_a1b2c3d4",
        workflow_id="wf_a1b2c3d4",
        current_state="DISCOVERING",
        execution_metadata=ExecutionMetadata(correlation_id="corr-test-budget"),
        workflow_metadata=WorkflowMetadata(niche="Dentist", location="Austin, TX", max_leads=5),
        timestamps=WorkflowTimestamps(
            created_at=now,
            updated_at=now,
            state_entered_at=now,
        )
    )
    
    # Direct invoke should trigger CostThresholdExceededError
    with pytest.raises(CostThresholdExceededError):
        await executor._execute_agent_run(dummy_agent, MagicMock(), DiscoveryLeadsSchema, context.session_id)
        
    # Test _record_worker_execution_result constructs execution result correctly
    mock_inv_result = WorkerInvocationResult(
        worker_name="dummy_worker",
        correlation_id="corr-test-budget",
        success=True,
        output=None,
        execution_duration_ms=450.0,
        retries_attempted=2
    )
    
    executor._record_worker_execution_result(context, mock_inv_result)
    
    # Check timeline
    timeline = executor._worker_timelines["sess_a1b2c3d4"]
    assert len(timeline) == 1
    exec_res = timeline[0]
    assert exec_res.success is True
    assert exec_res.worker_name == "dummy_worker"
    assert exec_res.runtime == 0.45
    assert exec_res.retries == 2
    assert exec_res.correlation_id == "corr-test-budget"
    
    # Trace entry check
    trace = executor.get_trace("sess_a1b2c3d4")
    assert trace is not None
    timeline_entry = next(entry for entry in trace.entries if entry.event_type == "worker_timeline")
    assert timeline_entry.details["worker_name"] == "dummy_worker"
    assert timeline_entry.details["runtime"] == 0.45
