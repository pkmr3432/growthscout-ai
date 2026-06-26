# tests/orchestrator_tests/test_checkpoint_sprint523.py
import sys
from unittest.mock import MagicMock, patch

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

import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.interfaces.checkpoint import (
    CheckpointInterface,
    CheckpointProviderFactory,
    WorkflowCheckpoint,
)
from agents.orchestrator_agent.interfaces.in_memory_checkpoint import InMemoryCheckpointInterface
from agents.orchestrator_agent.interfaces.firestore_checkpoint import FirestoreCheckpointInterface
from agents.orchestrator_agent.exceptions import CheckpointConflictError, CheckpointNotFoundError
from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
)
from agents.orchestrator_agent.run_budget import WorkflowRunBudget
from agents.orchestrator_agent.state_machine.states import WorkflowState
from agents.orchestrator_agent.workflow_executor import WorkflowExecutor, TransitionPlan
from agents.orchestrator_agent.runtime_services import RuntimeServices

def _now():
    return datetime.now(timezone.utc)

def _make_context(session_id="sess_test1234") -> WorkflowContext:
    now = _now()
    return WorkflowContext(
        session_id=session_id,
        workflow_id="wf_abcd1234",
        current_state=WorkflowState.IDLE,
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="plumbing", location="Austin, TX"),
        timestamps=WorkflowTimestamps(created_at=now, updated_at=now, state_entered_at=now),
    )

def test_in_memory_backend_conformance():
    ci = InMemoryCheckpointInterface()
    ctx = _make_context("sess_11112222")
    
    # next_version initial
    assert ci.next_version(ctx.session_id) == 1
    
    cp = CheckpointInterface.build(ctx, [], 1)
    ci.save(cp)
    
    # next_version increments
    assert ci.next_version(ctx.session_id) == 2
    
    # load latest
    restored = ci.load(ctx.session_id)
    assert restored.checkpoint_version == 1
    assert restored.session_id == ctx.session_id
    
    # list_versions
    assert ci.list_versions(ctx.session_id) == [1]
    
    # load specific version
    assert ci.load_version(ctx.session_id, 1).checkpoint_version == 1

def test_in_memory_concurrency_error():
    ci = InMemoryCheckpointInterface()
    ctx = _make_context("sess_33334444")
    
    cp1 = CheckpointInterface.build(ctx, [], 1)
    ci.save(cp1)
    
    # Save same version again should raise CheckpointConflictError
    cp2 = CheckpointInterface.build(ctx, [], 1)
    with pytest.raises(CheckpointConflictError):
        ci.save(cp2)
        
    # Save a higher version (e.g. 3) first, then try to save a lower version (e.g. 2)
    cp_high = CheckpointInterface.build(ctx, [], 3)
    ci.save(cp_high)
    
    cp_low = CheckpointInterface.build(ctx, [], 2)
    with pytest.raises(CheckpointConflictError):
        ci.save(cp_low)

@patch("google.cloud.firestore.Client")
def test_firestore_backend_conformance(mock_client_class):
    mock_db = MagicMock()
    mock_client_class.return_value = mock_db
    
    config = RuntimeConfig(checkpoint_backend="firestore")
    ci = CheckpointProviderFactory.create(config)
    assert isinstance(ci, FirestoreCheckpointInterface)
    
    # Setup mock collection and query for monotonic check
    mock_collection = MagicMock()
    mock_query = MagicMock()
    
    mock_db.collection.return_value = mock_collection
    mock_collection.where.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.limit.return_value = mock_query
    
    # Stream returns empty (meaning no previous checkpoints exist)
    mock_query.stream.return_value = []
    
    ctx = _make_context("sess_55556666")
    cp = CheckpointInterface.build(ctx, [], 1)
    
    # Mock doc set
    mock_doc = MagicMock()
    mock_collection.document.return_value = mock_doc
    
    ci.save(cp)
    mock_doc.set.assert_called_once()
    
    # Now simulate existing checkpoint v1 in Firestore when trying to save version 1 again
    mock_existing_doc = MagicMock()
    mock_existing_doc.to_dict.return_value = {"checkpoint_version": 1}
    mock_query.stream.return_value = [mock_existing_doc]
    
    with pytest.raises(CheckpointConflictError):
        ci.save(cp)

@patch("google.cloud.firestore.Client")
def test_firestore_auth_fallback(mock_client_class):
    # Raise exception on firestore client init
    mock_client_class.side_effect = Exception("Auth failed")
    
    config = RuntimeConfig(checkpoint_backend="firestore")
    ci = CheckpointProviderFactory.create(config)
    # Factory must fall back gracefully to InMemoryCheckpointInterface
    assert isinstance(ci, InMemoryCheckpointInterface)

@pytest.mark.asyncio
async def test_budget_and_timeline_serialization_and_restore():
    config = RuntimeConfig(checkpoint_backend="in_memory")
    ci = InMemoryCheckpointInterface()
    
    # Create budget and record operations
    budget = WorkflowRunBudget(
        max_gemini_requests=5,
        gemini_requests=2,
        estimated_cost=0.004
    )
    
    ctx = _make_context("sess_77778888")
    ctx = ctx.model_copy(update={"budget": budget})
    
    # Construct minimal services and executor
    from agents.orchestrator_agent.protocols import SystemClock
    from agents.orchestrator_agent.metrics_collector import InMemoryMetricsCollector
    from agents.orchestrator_agent.interfaces.events import StdoutEventPublisher
    from agents.orchestrator_agent.hooks.audit_trail import AuditTrailWriter
    from agents.orchestrator_agent.circuit_breaker import CircuitBreakerRegistry
    from agents.orchestrator_agent.failure_policy import FailurePolicy
    from agents.orchestrator_agent.cache_layer import RuntimeCacheManager
    from agents.orchestrator_agent.interfaces.worker_invocation import WorkerRegistry, WorkerExecutionResult
    
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
        checkpoint_interface=ci,
        worker_registry=WorkerRegistry(),
        preflight_validator=MagicMock(),
    )
    
    executor = WorkflowExecutor(services=services)
    
    # Record timeline entry
    res = WorkerExecutionResult(
        success=True,
        worker_name="dummy_worker",
        output=None,
        metrics={"gemini_requests": 1},
        evidence=[],
        runtime=1.2,
        retries=0,
        correlation_id="corr-round"
    )
    if not hasattr(executor, "_worker_timelines"):
        executor._worker_timelines = {}
    executor._worker_timelines[ctx.session_id] = [res]
    
    # Save state plan
    plan = TransitionPlan(
        target_state=WorkflowState.DISCOVERING,
        create_checkpoint=True,
        publish_events=False
    )
    
    # Apply plan which triggers checkpoint save
    new_context = executor._apply_transition_plan(ctx, plan, "orchestrator_agent", "Transition test")
    
    # Verify budget and timeline are stored in checkpoint
    checkpoint = ci.load(ctx.session_id)
    assert checkpoint.context_snapshot.budget is not None
    assert checkpoint.context_snapshot.budget.gemini_requests == 2
    assert len(checkpoint.context_snapshot.worker_timeline) == 1
    assert checkpoint.context_snapshot.worker_timeline[0]["worker_name"] == "dummy_worker"
    
    # Now simulate restoring
    restored_executor = WorkflowExecutor(services=services)
    with patch.object(restored_executor, "execute_step", side_effect=Exception("Break loop")):
        try:
            await restored_executor.execute_to_gate(checkpoint.context_snapshot)
        except Exception:
            pass
            
    # Verify budget and timeline are correctly restored inside executor variables
    restored_budget = restored_executor._get_or_create_budget(ctx.session_id)
    assert restored_budget.gemini_requests == 2
    
    restored_timeline = restored_executor._worker_timelines[ctx.session_id]
    assert len(restored_timeline) == 1
    assert restored_timeline[0].worker_name == "dummy_worker"
    assert restored_timeline[0].runtime == 1.2
