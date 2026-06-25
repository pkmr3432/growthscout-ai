# tests/orchestrator_tests/test_transition_controller.py
"""
Tests: TransitionController pure validation.

Validates:
  - APPROVED for valid orchestrator-initiated transitions
  - DENIED_UNAUTHORIZED_AGENT when acting_agent != "orchestrator_agent"
  - DENIED_TERMINAL_STATE when current_state is terminal
  - DENIED_INVALID_TRANSITION when target not in allowed_transitions
  - TransitionResult fields are always populated (no None audit_entry)
  - TransitionController never mutates WorkflowContext
"""
import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.state_machine.transition_controller import (
    TransitionController,
    TransitionValidationStatus,
    TransitionResult,
    MemoryAction,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState
from agents.orchestrator_agent.hooks.audit_trail import AuditTrailEntry


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_context(state: WorkflowState = WorkflowState.IDLE):
    from agents.orchestrator_agent.state_machine.workflow_context import (
        WorkflowContext, WorkflowMetadata, ExecutionMetadata, WorkflowTimestamps
    )
    now = datetime.now(timezone.utc)
    return WorkflowContext(
        session_id="sess_abcd1234",
        workflow_id="wf_abcd1234",
        current_state=state,
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="plumbing", location="Austin, TX"),
        timestamps=WorkflowTimestamps(
            created_at=now, updated_at=now, state_entered_at=now
        ),
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestTransitionControllerApproval:
    def test_approved_valid_transition(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(
            context=ctx,
            requested_next=WorkflowState.DISCOVERING,
            acting_agent="orchestrator_agent",
            reason="Starting pipeline.",
        )
        assert result.is_valid is True
        assert result.validation_status == TransitionValidationStatus.APPROVED
        assert result.denial_reason is None

    def test_approved_result_has_correct_states(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(ctx, WorkflowState.DISCOVERING, "orchestrator_agent", "ok")
        assert result.previous_state == WorkflowState.IDLE
        assert result.next_state == WorkflowState.DISCOVERING

    def test_approved_result_has_audit_entry(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(ctx, WorkflowState.DISCOVERING, "orchestrator_agent", "ok")
        assert result.audit_entry is not None
        assert isinstance(result.audit_entry, AuditTrailEntry)

    def test_approved_result_has_memory_actions(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(ctx, WorkflowState.DISCOVERING, "orchestrator_agent", "ok")
        # DISCOVERING writes to session_memory and business_profiles
        assert isinstance(result.required_memory_actions, list)
        domains = [a.domain for a in result.required_memory_actions]
        assert "session_memory" in domains or "business_profiles" in domains


class TestTransitionControllerDenials:
    def test_denied_unauthorized_agent(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(
            context=ctx,
            requested_next=WorkflowState.DISCOVERING,
            acting_agent="business_discovery_agent",  # Not allowed
            reason="Worker trying to transition.",
        )
        assert result.is_valid is False
        assert result.validation_status == TransitionValidationStatus.DENIED_UNAUTHORIZED_AGENT
        assert result.denial_reason is not None

    def test_denied_from_terminal_completed(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.COMPLETED)
        result = tc.validate(
            context=ctx,
            requested_next=WorkflowState.DISCOVERING,
            acting_agent="orchestrator_agent",
            reason="Attempt to restart from terminal.",
        )
        assert result.is_valid is False
        assert result.validation_status == TransitionValidationStatus.DENIED_TERMINAL_STATE

    def test_denied_from_terminal_failed(self):
        tc = TransitionController()
        ctx = _make_context(WorkflowState.FAILED)
        result = tc.validate(ctx, WorkflowState.DISCOVERING, "orchestrator_agent", "retry")
        assert result.is_valid is False
        assert result.validation_status == TransitionValidationStatus.DENIED_TERMINAL_STATE

    def test_denied_invalid_transition(self):
        tc = TransitionController()
        # IDLE cannot go directly to OPPORTUNITY_ANALYSIS
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(
            context=ctx,
            requested_next=WorkflowState.OPPORTUNITY_ANALYSIS,
            acting_agent="orchestrator_agent",
            reason="Skip to analysis.",
        )
        assert result.is_valid is False
        assert result.validation_status == TransitionValidationStatus.DENIED_INVALID_TRANSITION

    def test_denied_result_always_has_audit_entry(self):
        """Denial results must still produce a pre-built audit entry."""
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        result = tc.validate(ctx, WorkflowState.OPPORTUNITY_ANALYSIS, "orchestrator_agent", "bad")
        assert result.audit_entry is not None

    def test_worker_cannot_initiate_transition(self):
        """All worker names must be denied."""
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        for worker in [
            "business_discovery_agent",
            "website_analysis_agent",
            "opportunity_agent",
            "growth_intelligence_agent",
        ]:
            result = tc.validate(ctx, WorkflowState.DISCOVERING, worker, "worker attempt")
            assert result.is_valid is False
            assert result.validation_status == TransitionValidationStatus.DENIED_UNAUTHORIZED_AGENT


class TestTransitionControllerImmutability:
    def test_original_context_unchanged_after_validation(self):
        """TransitionController must never modify the input WorkflowContext."""
        tc = TransitionController()
        ctx = _make_context(WorkflowState.IDLE)
        original_state = ctx.current_state
        tc.validate(ctx, WorkflowState.DISCOVERING, "orchestrator_agent", "ok")
        assert ctx.current_state == original_state, (
            "TransitionController must not mutate WorkflowContext."
        )


class TestMemoryAction:
    def test_memory_action_creation(self):
        action = MemoryAction(operation="write", domain="session_memory", keys=["leads"], policy="overwrite")
        assert action.operation == "write"
        assert action.domain == "session_memory"
