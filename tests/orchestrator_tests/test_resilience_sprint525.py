import sys
from unittest.mock import MagicMock
# Dynamically stub google.cloud.firestore if not installed
try:
    from google.cloud import firestore
except ModuleNotFoundError:
    mock_firestore = MagicMock()
    mock_firestore.Query.DESCENDING = "DESCENDING"
    sys.modules["google.cloud.firestore"] = mock_firestore
    sys.modules["google.cloud"] = MagicMock()
    sys.modules["google.cloud"].firestore = mock_firestore
    firestore = mock_firestore

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from agents.orchestrator_agent.agent import OrchestratorDependencies, GrowthScoutOrchestrator
from agents.orchestrator_agent.workflow_executor import WorkflowExecutor, TransitionPlan
from agents.orchestrator_agent.state_machine.states import WorkflowState, StateType
from agents.orchestrator_agent.state_machine.workflow_context import WorkflowContext, WorkflowMetadata, ExecutionMetadata, WorkflowTimestamps
from agents.orchestrator_agent.exceptions import (
    InvalidTransitionError,
    EvidenceValidationError,
    SchemaValidationError,
    BusinessValidationError,
)
from agents.orchestrator_agent.error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from agents.orchestrator_agent.interfaces.checkpoint import CheckpointInterface, WorkflowCheckpoint
from agents.orchestrator_agent.interfaces.in_memory_checkpoint import InMemoryCheckpointInterface
from agents.orchestrator_agent.interfaces.firestore_checkpoint import FirestoreCheckpointInterface
from agents.orchestrator_agent.circuit_breaker import CircuitBreaker, CircuitBreakerRegistry, CircuitState
from agents.orchestrator_agent.service_names import ServiceName
from agents.orchestrator_agent.hooks.audit_trail import AuditEventType, AuditTrailEntry
from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.metrics_collector import InMemoryMetricsCollector

from agents.shared.schemas import (
    DiscoveryLead,
    DiscoveryLeadsSchema,
    AuditResultsSchema,
    AuditResults,
    AuditSeoData,
    OpportunityAnalysisSchema,
    CategoryScores,
    GrowthReportsSchema,
)

from tests.orchestrator_tests.failure_injector import FailureInjector

# Helpers for context and metadata

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_timestamps(elapsed_seconds: float = 0.0) -> WorkflowTimestamps:
    now = _now()
    created = now - timedelta(seconds=elapsed_seconds)
    return WorkflowTimestamps(
        created_at=created,
        updated_at=now,
        state_entered_at=now,
    )


def _make_context(state: WorkflowState = WorkflowState.IDLE, elapsed_seconds: float = 0.0) -> WorkflowContext:
    from agents.orchestrator_agent.run_budget import WorkflowRunBudget
    # Populate start_time in budget matching created_at
    created = _now() - timedelta(seconds=elapsed_seconds)
    budget = WorkflowRunBudget(
        start_time=created,
        max_gemini_requests=20,
        max_maps_requests=15,
        max_pages_crawled=10,
        max_elapsed_seconds=600.0,
        max_cost_limit=5.00
    )
    return WorkflowContext(
        session_id="sess_b2c3d4e5",
        workflow_id="wf_b2c3d4e5",
        current_state=state,
        execution_metadata=ExecutionMetadata(correlation_id="corr-999"),
        workflow_metadata=WorkflowMetadata(niche="Roofing", location="Denver, CO", max_leads=5),
        timestamps=_make_timestamps(elapsed_seconds),
        budget=budget,
    )


def _mock_discovery_leads() -> DiscoveryLeadsSchema:
    return DiscoveryLeadsSchema(
        leads=[
            DiscoveryLead(
                business_name="Denver Roof Experts",
                address="100 Colfax Ave, Denver, CO",
                website_url="http://denverroofs.com",
                website_status="Modern Website",
                google_rating=4.7,
                review_count=80,
                google_maps_place_id="place_denver_1"
            )
        ],
        competitor_candidates=[]
    )


@pytest.fixture
def base_setup():
    cfg = RuntimeConfig(
        worker_timeout_seconds=0.5,
        mcp_timeout_seconds=0.5,
        firestore_timeout_seconds=0.5,
        workflow_timeout_seconds=2.0,
        max_retries=2,
        backoff_factor=0.01,  # Keep delay short for tests
    )
    deps = OrchestratorDependencies(
        checkpoint_interface=InMemoryCheckpointInterface()
    )
    deps.worker_registry = MagicMock()
    deps.worker_registry.get.return_value = MagicMock()

    # Build services
    from agents.orchestrator_agent.protocols import SystemClock
    from agents.orchestrator_agent.preflight import PreflightValidator
    from agents.orchestrator_agent.cache_layer import RuntimeCacheManager
    from agents.orchestrator_agent.mcp_lifecycle import MCPLifecycleManager
    from agents.orchestrator_agent.failure_policy import FailurePolicy
    from agents.orchestrator_agent.runtime_services import RuntimeServices

    cbr = CircuitBreakerRegistry(
        failure_threshold=cfg.circuit_breaker_failure_threshold,
        cooldown_seconds=cfg.circuit_breaker_cooldown_seconds,
        success_threshold=cfg.circuit_breaker_success_threshold,
    )
    fp_resolved = FailurePolicy(config=cfg, cb_registry=cbr)
    
    services = RuntimeServices(
        config=cfg,
        cache_manager=RuntimeCacheManager(),
        metrics_collector=deps.metrics_collector,
        cb_registry=cbr,
        failure_policy=fp_resolved,
        clock=SystemClock(),
        event_publisher=deps.event_publisher,
        audit_writer=deps.audit_writer,
        checkpoint_interface=deps.checkpoint_interface,
        worker_registry=deps.worker_registry,
        preflight_validator=PreflightValidator(cfg),
        mcp_lifecycle=MCPLifecycleManager(),
    )

    executor = WorkflowExecutor(
        services=services,
        tc=deps.transition_controller,
        mg=deps.memory_governor,
        ev=deps.evidence_validator,
        rc=deps.resumability_controller,
    )
    return executor, services, deps, cfg


@pytest.mark.asyncio
async def test_retry_behavior_and_metrics(base_setup):
    """Test that a transient worker failure triggers configured retries and records retry metrics."""
    executor, services, deps, cfg = base_setup
    context = _make_context(WorkflowState.IDLE)
    
    injector = FailureInjector()
    with injector.activate():
        # Inject transient Gemini rate limits (retries allowed)
        injector.inject_failure("gemini", "quota_failure")

        # Mock execute agent run to fail transiently
        call_count = 0
        original_execute = executor._execute_agent_run
        async def mock_execute_agent_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # Raise quota failure for the first 2 attempts
                raise GrowthScoutRuntimeError(
                    error_code=RuntimeErrorCode.RATE_LIMIT,
                    message="429 transient limit",
                    service=ServiceName.GEMINI,
                    retryable=True
                )
            return _mock_discovery_leads()
        
        executor._execute_agent_run = mock_execute_agent_run

        # Execute only single step: IDLE -> DISCOVERING -> (runs business_discovery_agent)
        # We start directly from state DISCOVERING
        context = context.with_state(WorkflowState.DISCOVERING, _now())
        res_context = await executor.execute_step(context)

        # Confirm step successfully completed on the 3rd attempt (after 2 retries)
        assert res_context.current_state == WorkflowState.LEAD_PARTITIONING
        assert call_count == 3
        
        # Verify retry metrics
        metrics = executor._mc.get_metrics(context.session_id)
        assert metrics["worker_retries_total"] == 2
        assert metrics["retry_attempts"] == 2

        # Verify retry audit entries
        trail = executor._aw.read_trail(context.session_id)
        retry_started_events = [e for e in trail if e.event_type == AuditEventType.RETRY_STARTED]
        retry_completed_events = [e for e in trail if e.event_type == AuditEventType.RETRY_COMPLETED]
        assert len(retry_started_events) == 2
        assert len(retry_completed_events) == 1


@pytest.mark.asyncio
async def test_validation_errors_never_retried(base_setup):
    """Test that SchemaValidationError and BusinessValidationError bypass the retry policy entirely."""
    executor, services, deps, cfg = base_setup
    context = _make_context(WorkflowState.DISCOVERING)

    # Mock execute agent run to raise SchemaValidationError directly
    call_count = 0
    async def mock_execute_agent_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise SchemaValidationError("Fails schema checks")
    executor._execute_agent_run = mock_execute_agent_run

    res_context = await executor.execute_step(context)

    # Confirm it immediately transitioned to FAILED and didn't retry
    assert res_context.current_state == WorkflowState.FAILED
    assert call_count == 1
    
    # Confirm no retries recorded
    metrics = executor._mc.get_metrics(context.session_id)
    assert metrics["worker_retries_total"] == 0


@pytest.mark.asyncio
async def test_worker_timeout_handling(base_setup):
    """Test that worker execution times out and is recovered according to FailurePolicy."""
    executor, services, deps, cfg = base_setup
    context = _make_context(WorkflowState.DISCOVERING)

    injector = FailureInjector()
    with injector.activate():
        # Inject Gemini timeout
        injector.inject_failure("gemini", "timeout")

        res_context = await executor.execute_step(context)

        # Worker invocation will time out and exhaust all 2 retries, leading to FAILED
        assert res_context.current_state == WorkflowState.FAILED
        
        # Verify timeout metrics and audits
        metrics = executor._mc.get_metrics(context.session_id)
        assert metrics["timeout_count"] > 0

        trail = executor._aw.read_trail(context.session_id)
        timeout_events = [e for e in trail if e.event_type == AuditEventType.TIMEOUT_OCCURRED]
        assert len(timeout_events) > 0


@pytest.mark.asyncio
async def test_workflow_timeout_enforcement(base_setup):
    """Test that overall workflow execution limit halts loop and transitions to FAILED."""
    executor, services, deps, cfg = base_setup
    
    # Set created_at to be older than timeout limits
    context = _make_context(WorkflowState.DISCOVERING, elapsed_seconds=10.0)

    # Run step execution
    res_context = await executor.execute_step(context)

    # Confirm it immediately transitioned to FAILED due to workflow timeout
    assert res_context.current_state == WorkflowState.FAILED
    
    # Check metrics and audits
    metrics = executor._mc.get_metrics(context.session_id)
    assert metrics["timeout_count"] == 1

    trail = executor._aw.read_trail(context.session_id)
    timeout_events = [e for e in trail if e.event_type == AuditEventType.TIMEOUT_OCCURRED]
    assert len(timeout_events) == 1
    assert timeout_events[0].transition_reason == "Workflow execution timeout occurred (limit: 2.0s)"


@pytest.mark.asyncio
async def test_circuit_breaker_transitions_and_callbacks(base_setup):
    """Test CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED) and callbacks."""
    executor, services, deps, cfg = base_setup
    
    # Custom low-threshold breaker for test
    cb = CircuitBreaker(
        name=ServiceName.GEMINI,
        failure_threshold=2,
        cooldown_seconds=0.1,
        success_threshold=1,
    )
    
    transitions = []
    def callback(name, old_state, new_state):
        transitions.append((name, old_state, new_state))
        
    cb.state_transition_callback = callback

    # Start CLOSED
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # 1. First failure
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # 2. Second failure -> Transitions to OPEN
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    assert len(transitions) == 1
    assert transitions[0] == (ServiceName.GEMINI, CircuitState.CLOSED, CircuitState.OPEN)

    # 3. Check cooldown and allow request -> Transitions to HALF_OPEN
    await asyncio.sleep(0.15)
    assert cb.allow_request() is True
    assert cb.state == CircuitState.HALF_OPEN
    assert len(transitions) == 2
    assert transitions[1] == (ServiceName.GEMINI, CircuitState.OPEN, CircuitState.HALF_OPEN)

    # 4. Record success -> Transitions to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert len(transitions) == 3
    assert transitions[2] == (ServiceName.GEMINI, CircuitState.HALF_OPEN, CircuitState.CLOSED)


@pytest.mark.asyncio
async def test_mcp_circuit_breaker_and_health(base_setup):
    """Test MCP circuit breaker rejection and health stats updates."""
    executor, services, deps, cfg = base_setup
    context = _make_context(WorkflowState.AUDITING)

    # Force the Web Analyzer MCP breaker OPEN
    mcp_service = ServiceName.WEB_ANALYZER_MCP
    cb = executor.services.cb_registry.get_breaker(mcp_service)
    cb._transition_to(CircuitState.OPEN)

    # Try executing website analysis step which uses Web Analyzer MCP
    # Set context discovery results so website analysis can run
    context = context.model_copy(update={"discovery_results": _mock_discovery_leads()})
    
    async def mock_execute_agent_run(agent_instance, request, output_schema, session_id=None):
        cb = executor.services.cb_registry.get_breaker(mcp_service)
        if not cb.allow_request():
            if session_id:
                executor.services.metrics_collector.record_service_request(session_id, mcp_service, "reject")
            raise GrowthScoutRuntimeError(
                error_code=RuntimeErrorCode.CIRCUIT_BREAKER_OPEN,
                message=f"Circuit breaker is OPEN for MCP service: {mcp_service.value}",
                service=mcp_service,
                retryable=False,
                correlation_id=request.correlation_id,
            )
        return MagicMock()
    executor._execute_agent_run = mock_execute_agent_run

    res_context = await executor.execute_step(context)

    # Confirm rejection triggers FAILED state
    assert res_context.current_state == WorkflowState.FAILED

    # Check metrics
    metrics = executor._mc.snapshot(context.session_id)
    assert metrics.service_metrics[mcp_service.value]["rejected_requests"] == 1


@pytest.mark.asyncio
async def test_firestore_circuit_breaker_and_timeout(base_setup):
    """Test Firestore checkpoint operation timeouts and circuit breaker checks."""
    executor, services, deps, cfg = base_setup
    
    # Configure Firestore backend
    cfg = cfg.model_copy(update={"checkpoint_backend": "firestore"})
    
    # Mock Firestore collection/document calls
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_query = MagicMock()
    mock_db.collection.return_value = mock_collection
    mock_collection.where.return_value = mock_collection
    mock_collection.order_by.return_value = mock_collection
    mock_collection.limit.return_value = mock_query
    mock_query.stream.return_value = [] # No concurrent versions
    
    fs_interface = FirestoreCheckpointInterface(cfg, cb_registry=services.cb_registry, metrics_collector=services.metrics_collector)
    fs_interface.db = mock_db

    # Tripping Firestore circuit breaker
    cb = services.cb_registry.get_breaker(ServiceName.FIRESTORE)
    cb._transition_to(CircuitState.OPEN)

    # Try calling save checkpoint, should fail with circuit breaker OPEN
    checkpoint = CheckpointInterface.build(
        context=_make_context(WorkflowState.DISCOVERING),
        audit_trail=[],
        checkpoint_version=1
    )

    with pytest.raises(GrowthScoutRuntimeError) as exc_info:
        fs_interface.save(checkpoint)

    assert exc_info.value.error_code == RuntimeErrorCode.CIRCUIT_BREAKER_OPEN
    assert exc_info.value.service == ServiceName.FIRESTORE

    # Verify metrics show reject
    metrics = services.metrics_collector.snapshot(checkpoint.session_id)
    assert metrics.service_metrics[ServiceName.FIRESTORE.value]["rejected_requests"] == 1


@pytest.mark.asyncio
async def test_graceful_recovery_and_serialization(base_setup):
    """Test that workflow resumption recovers context, budget, timeline, metrics, and tracks recovery ID."""
    executor, services, deps, cfg = base_setup
    
    # Setup first execution state
    context = _make_context(WorkflowState.DISCOVERING)
    
    # Record some mock metrics
    services.metrics_collector.record_transition(context.session_id, "IDLE", "DISCOVERING")
    services.metrics_collector.record_worker_retry(context.session_id, "business_discovery_agent")
    
    # Record some timelines
    from agents.orchestrator_agent.interfaces.worker_invocation import WorkerExecutionResult
    res_timeline = WorkerExecutionResult(
        worker_name="business_discovery_agent",
        correlation_id="corr-999",
        success=True,
        runtime=0.2,
        retries=1
    )
    executor._worker_timelines[context.session_id] = [res_timeline]

    # Save checkpoint
    plan = TransitionPlan(
        target_state=WorkflowState.LEAD_PARTITIONING,
        context_patch={"discovery_results": _mock_discovery_leads()},
        create_checkpoint=True,
        publish_events=False
    )
    
    # Execute apply transition plan which serializes state, budget, timeline, and metrics to checkpoint
    res_context = executor._apply_transition_plan(context, plan, "orchestrator_agent", "transition test")

    # Instantiate Orchestrator to attempt recovery
    from agents.orchestrator_agent.agent import GrowthScoutOrchestrator
    orch = GrowthScoutOrchestrator(deps, services=services)

    # Attempt resume
    success, recovered_context = orch.attempt_resume(context.session_id)
    
    assert success is True
    assert recovered_context is not None
    assert recovered_context.current_state == WorkflowState.LEAD_PARTITIONING
    assert recovered_context.discovery_results is not None
    assert recovered_context.recovery_id is not None
    assert recovered_context.recovery_id.startswith("rec_")

    # Verify metrics were fully restored from checkpoint
    metrics = services.metrics_collector.get_metrics(context.session_id)
    assert metrics["transitions_total"] == 2
    assert metrics["worker_retries_total"] == 1
    assert metrics["resumed_workflows"] == 1
    assert metrics["checkpoint_restores_total"] == 1

    # Verify recovery duration recorded
    snapshot = services.metrics_collector.snapshot(context.session_id)
    assert snapshot.recovery_duration_ms > 0.0

    # Verify audit event for recovery exists and carries recovery_id
    trail = services.audit_writer.read_trail(context.session_id)
    resumed_events = [e for e in trail if e.event_type == AuditEventType.WORKFLOW_RESUMED]
    assert len(resumed_events) == 1
    assert resumed_events[0].recovery_id == recovered_context.recovery_id


@pytest.mark.asyncio
async def test_failure_injection_scenarios(base_setup):
    """Test various injected failure modes (auth failures, networks drops, partial checkpoint writes)."""
    executor, services, deps, cfg = base_setup
    context = _make_context(WorkflowState.DISCOVERING)

    injector = FailureInjector()
    with injector.activate():
        # Scenario A: Injected Gemini Authentication Failure
        injector.inject_failure("gemini", "auth_failure")
        res_context = await executor.execute_step(context)
        assert res_context.current_state == WorkflowState.FAILED

        # Scenario B: Injected Network Interruption
        injector.clear()
        injector.inject_failure("network", "interruption")
        # Run step, should trigger retries and then fail
        res_context2 = await executor.execute_step(context)
        assert res_context2.current_state == WorkflowState.FAILED
        
        # Scenario C: Injected Partial Checkpoint Write (Simulated Crash)
        injector.clear()
        cfg = cfg.model_copy(update={"checkpoint_backend": "firestore"})
        
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_query = MagicMock()
        mock_db.collection.return_value = mock_collection
        mock_collection.where.return_value = mock_collection
        mock_collection.order_by.return_value = mock_collection
        mock_collection.limit.return_value = mock_query
        mock_query.stream.return_value = []
        
        fs_interface = FirestoreCheckpointInterface(cfg, cb_registry=services.cb_registry, metrics_collector=services.metrics_collector)
        fs_interface.db = mock_db
        
        injector.inject_failure("checkpoint", "partial_write")
        
        checkpoint = CheckpointInterface.build(
            context=_make_context(WorkflowState.DISCOVERING),
            audit_trail=[],
            checkpoint_version=1
        )
        
        # The partial write will succeed in writing document but raise RuntimeError simulating crash
        with pytest.raises(RuntimeError) as exc_info:
            fs_interface.save(checkpoint)
        assert "partial checkpoint write occurred" in str(exc_info.value)
