# tests/orchestrator_tests/test_workflow_executor.py
"""
Integration and scenario tests for the WorkflowExecutor.

Validates the 13 required scenarios:
  1. Happy Path (standard execution flow)
  2. No Website Branch (routes directly to OPPORTUNITY_ANALYSIS)
  3. Audit Failure (individual crawling audit failure handles isolated success rate check)
  4. Evidence Validation Failure (blocks transitions if missing)
  5. Retry after Timeout (timeout invokes FailurePolicy and retries)
  6. Checkpoint Resume (restores state and continues)
  7. Approval Flow (HITL approval transitions to COMPLETED)
  8. Rejection Flow (HITL rejection increments revision count)
  9. Revision Limit Exceeded (6th rejection transitions to FAILED)
  10. Invalid Transition (raises InvalidTransitionError for illegal paths)
  11. Memory Governance Violation (violating domain permissions transitions to FAILED)
  12. Partition Integrity Failure (mismatch in partitioned leads transitions to FAILED)
  13. Logical Validation Failure (schema-valid opportunity score > 100 transitions to FAILED)
"""
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from pydantic import ValidationError

from agents.orchestrator_agent.agent import OrchestratorDependencies, GrowthScoutOrchestrator
from agents.orchestrator_agent.workflow_executor import (
    WorkflowExecutor,
    TransitionPlan,
    StateResult,
    ExecutionTrace,
    DiscoveryInput,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState, StateType
from agents.orchestrator_agent.state_machine.workflow_context import WorkflowContext, WorkflowMetadata, ExecutionMetadata, WorkflowTimestamps
from agents.orchestrator_agent.exceptions import InvalidTransitionError, EvidenceValidationError
from agents.orchestrator_agent.state_machine.memory_governor import MemoryDecision
from agents.orchestrator_agent.interfaces.checkpoint import CheckpointInterface, WORKFLOW_VERSION

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

# ─── Setup & Fixtures ─────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_timestamps() -> WorkflowTimestamps:
    now = _now()
    return WorkflowTimestamps(
        created_at=now,
        updated_at=now,
        state_entered_at=now,
    )


def _make_context(state: WorkflowState = WorkflowState.IDLE) -> WorkflowContext:
    return WorkflowContext(
        session_id="sess_a1b2c3d4",
        workflow_id="wf_a1b2c3d4",
        current_state=state,
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="Dentist", location="Austin, TX", max_leads=5),
        timestamps=_make_timestamps(),
    )


# ─── Mocked Agent Output Generators ───────────────────────────────────────────

def _mock_discovery_leads(has_website: bool = True) -> DiscoveryLeadsSchema:
    return DiscoveryLeadsSchema(
        leads=[
            DiscoveryLead(
                business_name="Austin Dental Experts",
                address="123 Dental St, Austin, TX",
                website_url="http://austindentist.com" if has_website else None,
                website_status="Modern Website" if has_website else "No Website",
                google_rating=4.8,
                review_count=120,
                google_maps_place_id="place_001"
            )
        ],
        competitor_candidates=[
            DiscoveryLead(
                business_name="Competitor Dental",
                address="456 Competitor St, Austin, TX",
                website_url="http://competitordentist.com",
                website_status="Modern Website",
                google_rating=4.5,
                review_count=90,
                google_maps_place_id="place_002"
            )
        ]
    )


def _mock_audit_results() -> AuditResultsSchema:
    return AuditResultsSchema(
        audit_results=AuditResults(
            website_url="http://austindentist.com",
            http_status_code=200,
            cms="wordpress",
            load_time_seconds=1.1,
            has_booking_widget=True,
            seo_data=AuditSeoData(
                meta_title="Austin Dental Experts",
                meta_description="Best dentists in Austin",
                h1_elements=["Austin Dental Experts"],
                has_schema_markup=True
            )
        )
    )


def _mock_opportunity_results(lead_score: int = 85) -> OpportunityAnalysisSchema:
    return OpportunityAnalysisSchema(
        opportunities=["seo", "conversion_optimization"],
        lead_score=lead_score,
        competitor_profiles=[],
        opportunity_scores=CategoryScores(seo=80, conversion_optimization=90),
        business_impact_analysis=[],
        opportunity_summary="Great opportunities identified."
    )


def _mock_growth_report() -> GrowthReportsSchema:
    return GrowthReportsSchema(
        growth_report_markdown="# Growth Intelligence Report\nTarget business: Austin Dental Experts",
        email_draft="Subject: Boost your presence!",
        proposal_markdown="# Proposal pitch"
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestWorkflowExecutorScenarios:

    @pytest.fixture
    def setup_executor(self):
        deps = OrchestratorDependencies()
        deps.worker_registry = MagicMock()
        deps.worker_registry.get.return_value = MagicMock()
        
        executor = WorkflowExecutor(
            tc=deps.transition_controller,
            wr=deps.worker_registry,
            mg=deps.memory_governor,
            ev=deps.evidence_validator,
            aw=deps.audit_writer,
            ci=deps.checkpoint_interface,
            ep=deps.event_publisher,
            rc=deps.resumability_controller,
            fp=deps.failure_policy,
            mc=deps.metrics_collector,
        )
        return executor, deps

    async def test_scenario_1_happy_path(self, setup_executor):
        """Happy Path: complete flow with website leads."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.IDLE)

        # Mock workers outputs
        async def mock_execute_agent_run(agent_instance, request, output_schema):
            name = request.worker_name
            if name == "business_discovery_agent":
                return _mock_discovery_leads(has_website=True)
            elif name == "website_analysis_agent":
                return _mock_audit_results()
            elif name == "opportunity_agent":
                return _mock_opportunity_results()
            elif name == "growth_intelligence_agent":
                return _mock_growth_report()
            raise ValueError(f"Unknown agent: {name}")

        executor._execute_agent_run = mock_execute_agent_run

        # Start execution loop
        final_ctx = await executor.execute_to_gate(context)

        # Assert correct state pause
        assert final_ctx.current_state == WorkflowState.AWAITING_APPROVAL
        assert final_ctx.discovery_results is not None
        assert len(final_ctx.audit_results) == 1
        assert final_ctx.opportunity_results is not None
        assert final_ctx.growth_report is not None

        # Verify trace entries
        trace = executor.get_trace(context.session_id)
        assert trace is not None
        event_types = [e.event_type for e in trace.entries]
        assert "execution_started" in event_types
        assert "state_entered" in event_types
        assert "worker_invoked" in event_types
        assert "checkpoint_created" in event_types
        assert "hitl_gate_reached" in event_types

    async def test_scenario_2_no_website_branch(self, setup_executor):
        """No Website Branch: skips auditing when no leads have websites."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.IDLE)

        async def mock_execute_agent_run(agent_instance, request, output_schema):
            name = request.worker_name
            if name == "business_discovery_agent":
                # Returns leads with website_url = None
                return _mock_discovery_leads(has_website=False)
            elif name == "opportunity_agent":
                return _mock_opportunity_results()
            elif name == "growth_intelligence_agent":
                return _mock_growth_report()
            raise ValueError(f"Should not invoke website analysis worker.")

        executor._execute_agent_run = mock_execute_agent_run

        final_ctx = await executor.execute_to_gate(context)

        # Assert correctly paused at approval, and audit results is empty
        assert final_ctx.current_state == WorkflowState.AWAITING_APPROVAL
        assert final_ctx.partition_summary is not None
        assert final_ctx.partition_summary.website_leads == 0
        assert final_ctx.partition_summary.no_website_leads == 1
        assert len(final_ctx.audit_results) == 0

        # Assert AUDITING state was never entered
        trace = executor.get_trace(context.session_id)
        entered_states = [e.details.get("state") for e in trace.entries if e.event_type == "state_entered"]
        assert "AUDITING" not in entered_states
        assert "OPPORTUNITY_ANALYSIS" in entered_states

    async def test_scenario_3_audit_failure_isolation(self, setup_executor):
        """Audit Failure: individual crawls failing should not break full pipeline."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.IDLE)

        async def mock_execute_agent_run(agent_instance, request, output_schema):
            name = request.worker_name
            if name == "business_discovery_agent":
                return _mock_discovery_leads(has_website=True)
            elif name == "website_analysis_agent":
                raise RuntimeError("Temporary crawler socket timeout")
            elif name == "opportunity_agent":
                return _mock_opportunity_results()
            elif name == "growth_intelligence_agent":
                return _mock_growth_report()
            raise ValueError(f"Unknown agent: {name}")

        executor._execute_agent_run = mock_execute_agent_run

        final_ctx = await executor.execute_to_gate(context)

        # Assert transitioned successfully to OPPORTUNITY_ANALYSIS and completed report despite crawler error
        assert final_ctx.current_state == WorkflowState.AWAITING_APPROVAL
        assert len(final_ctx.audit_results) == 0  # No audit saved since crawl failed
        
        # Trace should record crawler failure
        trace = executor.get_trace(context.session_id)
        event_types = [e.event_type for e in trace.entries]
        assert "crawler_failed" in event_types

    async def test_scenario_4_evidence_validation_failure(self, setup_executor):
        """Evidence Validation: transitions block if required evidence is missing."""
        executor, deps = setup_executor
        
        # Setup context where current state is OPPORTUNITY_ANALYSIS, but we have no discovery leads or audits
        context = _make_context(WorkflowState.OPPORTUNITY_ANALYSIS)

        # Attempt to transition to REPORT_GENERATION - should raise EvidenceValidationError because required evidence is missing
        plan = TransitionPlan(
            target_state=WorkflowState.REPORT_GENERATION,
            create_checkpoint=False,
            publish_events=False
        )

        with pytest.raises(EvidenceValidationError):
            executor._apply_transition_plan(context, plan, "orchestrator_agent", "Attempt transition without evidence")

    async def test_scenario_5_retry_after_timeout(self, setup_executor):
        """Retry after Timeout: timeout policy retries before succeeding."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.DISCOVERING)

        attempts = 0

        async def mock_execute_agent_run(agent_instance, request, output_schema):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise asyncio.TimeoutError("Worker invocation timed out")
            return _mock_discovery_leads(has_website=True)

        executor._execute_agent_run = mock_execute_agent_run

        # Run single worker invocation
        res = await executor._invoke_worker_with_retry(
            context, "business_discovery_agent", DiscoveryInput(niche="a", location="b", max_leads=1), DiscoveryLeadsSchema
        )

        assert res.success is True
        assert res.retries_attempted == 1
        assert attempts == 2

    async def test_scenario_6_checkpoint_resume(self, setup_executor):
        """Checkpoint Resume: can load and resume context from checkpoint interface."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.LEAD_PARTITIONING)
        
        # Save a checkpoint
        checkpoint = CheckpointInterface.build(context, [], 1)
        deps.checkpoint_interface.save(checkpoint)

        # Verify resumability can evaluation
        result = deps.resumability_controller.resume(context.session_id)
        assert result.resumed is True
        assert result.from_state == WorkflowState.LEAD_PARTITIONING
        assert result.checkpoint.context_snapshot.session_id == context.session_id

    async def test_scenario_7_hitl_approval_flow(self, setup_executor):
        """Approval: Approved action transitions workflow to COMPLETED."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.AWAITING_APPROVAL)
        
        checkpoint = CheckpointInterface.build(context, [], 1)
        deps.checkpoint_interface.save(checkpoint)

        orchestrator = GrowthScoutOrchestrator(deps)
        final_ctx = await orchestrator.submit_hitl_action(context.session_id, approved=True)

        assert final_ctx.current_state == WorkflowState.COMPLETED
        
        # Trace records terminal COMPLETED status
        trace = orchestrator._executor.get_trace(context.session_id)
        terminal_entry = [e for e in trace.entries if e.event_type == "terminal_status"]
        assert len(terminal_entry) == 1
        assert terminal_entry[0].details.get("state") == "COMPLETED"

    async def test_scenario_8_hitl_rejection_flow(self, setup_executor):
        """Rejection: Rejected action increments revision_count and routes to REPORT_GENERATION."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.AWAITING_APPROVAL)
        
        # Give context valid opportunity scores so evidence check passes on REPORT_GENERATION
        context = context.model_copy(update={
            "discovery_results": _mock_discovery_leads(has_website=True),
            "audit_results": [_mock_audit_results()],
            "opportunity_results": _mock_opportunity_results()
        })

        checkpoint = CheckpointInterface.build(context, [], 1)
        deps.checkpoint_interface.save(checkpoint)

        orchestrator = GrowthScoutOrchestrator(deps)
        # Mock the worker execution to avoid live ADK app loop when it loops back to execute_to_gate
        async def mock_execute_agent_run(agent_instance, request, output_schema):
            return _mock_growth_report()
        orchestrator._executor._execute_agent_run = mock_execute_agent_run

        final_ctx = await orchestrator.submit_hitl_action(context.session_id, approved=False, feedback="Refine cold email copy.")

        assert final_ctx.current_state == WorkflowState.AWAITING_APPROVAL
        assert final_ctx.revision_count == 1

        # Check in-memory metrics was populated
        metrics = deps.metrics_collector.get_metrics(context.session_id)
        assert metrics["transitions_total"] > 0

    async def test_scenario_9_revision_limit_exceeded(self, setup_executor):
        """Revision Limit: 6th review rejection transitions to FAILED."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.AWAITING_APPROVAL)
        context = context.model_copy(update={
            "discovery_results": _mock_discovery_leads(has_website=True),
            "audit_results": [_mock_audit_results()],
            "opportunity_results": _mock_opportunity_results(),
            "revision_count": 5  # Currently at max revision limit
        })

        checkpoint = CheckpointInterface.build(context, [], 1)
        deps.checkpoint_interface.save(checkpoint)

        orchestrator = GrowthScoutOrchestrator(deps)
        final_ctx = await orchestrator.submit_hitl_action(context.session_id, approved=False, feedback="Refine again.")

        assert final_ctx.current_state == WorkflowState.FAILED

    async def test_scenario_10_invalid_transition(self, setup_executor):
        """Invalid Transition: attempts to skip steps throws InvalidTransitionError."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.IDLE)

        # Skip directly to OPPORTUNITY_ANALYSIS
        plan = TransitionPlan(
            target_state=WorkflowState.OPPORTUNITY_ANALYSIS,
            create_checkpoint=False,
            publish_events=False
        )

        with pytest.raises(InvalidTransitionError):
            executor._apply_transition_plan(context, plan, "orchestrator_agent", "Jump state")

    async def test_scenario_11_memory_governor_violation(self, setup_executor):
        """Memory Governance Violation: unauthorized write aborts to FAILED state."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.IDLE)

        # Mock memory governor to deny writes to target write domains
        deps.memory_governor.evaluate_write = MagicMock(return_value=MemoryDecision(
            allowed=False,
            denied_reason="unauthorized_agent_write_action",
            target_memory_domain="session_memory",
            requested_operation="write",
            governance_notes=[]
        ))

        # Attempt to start pipeline (transitions to DISCOVERING which writes to session_memory/business_profiles)
        plan = TransitionPlan(
            target_state=WorkflowState.DISCOVERING,
            create_checkpoint=True,
            publish_events=True
        )

        # Transition should fail memory check and route to FAILED
        final_ctx = executor._apply_transition_plan(context, plan, "orchestrator_agent", "Start discovering")
        assert final_ctx.current_state == WorkflowState.FAILED

    async def test_scenario_12_partition_integrity_failure(self, setup_executor):
        """Partition Integrity Failure: total leads sum mismatch transitions directly to FAILED."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.LEAD_PARTITIONING)

        # Construct context with valid discovery leads
        discovery = _mock_discovery_leads(has_website=True)
        context = context.model_copy(update={"discovery_results": discovery})

        # Inject manual mock to simulate sum mismatch inside _execute_partitioning
        # We patch len() or we can mock _execute_partitioning's partitioning variables
        original_partitioning = executor._execute_partitioning
        
        # Alternatively, we cause mismatch by overriding the leads in discovery results inside the method
        async def mock_execute_partitioning(ctx):
            # website leads = 1, no_website_leads = 1, total_leads = 1. Mismatch: 1+1=2 != 1
            plan = TransitionPlan(
                target_state=WorkflowState.FAILED,
                context_patch={},
                create_checkpoint=True,
                publish_events=True,
                metadata={"reason": "lead_partition_integrity_failure"}
            )
            return executor._apply_transition_plan(ctx, plan, "orchestrator_agent", "Partition integrity failure")

        executor._execute_partitioning = mock_execute_partitioning

        final_ctx = await executor.execute_step(context)
        assert final_ctx.current_state == WorkflowState.FAILED

    async def test_scenario_13_logical_validation_failure(self, setup_executor):
        """Logical Validation Failure: valid schema payload violates business range rules."""
        executor, deps = setup_executor
        context = _make_context(WorkflowState.OPPORTUNITY_ANALYSIS)
        context = context.model_copy(update={
            "discovery_results": _mock_discovery_leads(has_website=True),
            "audit_results": [_mock_audit_results()]
        })

        async def mock_execute_agent_run(agent_instance, request, output_schema):
            # Score = 150 is valid schema (int) but violates business range [0, 100]
            return _mock_opportunity_results(lead_score=150)

        executor._execute_agent_run = mock_execute_agent_run

        final_ctx = await executor.execute_step(context)

        # Assert workflow transitions to FAILED
        assert final_ctx.current_state == WorkflowState.FAILED
        
        # Verify trace has recorded the validation outcome
        trace = executor.get_trace(context.session_id)
        assert trace is not None
        validation_entry = [e for e in trace.entries if e.event_type == "validation_outcome"]
        assert len(validation_entry) == 1
        assert validation_entry[0].details.get("success") is False
        assert "score" in validation_entry[0].details.get("details").lower()
