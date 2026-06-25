# tests/orchestrator_tests/test_resumability.py
"""
Tests: ResumabilityController workflow resumption logic.

Validates:
  - Non-terminal state → resumed=True with correct from_state
  - Terminal state → resumed=False, denial_reason="terminal_state"
  - No checkpoint → resumed=False, denial_reason="no_checkpoint_found"
  - Schema version mismatch → resumed=False, denial_reason="schema_version_mismatch"
  - can_resume() and resume() behave identically
"""
import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.interfaces.checkpoint import (
    CheckpointInterface,
    WorkflowCheckpoint,
    CURRENT_SCHEMA_VERSION,
)
from agents.orchestrator_agent.interfaces.resumability import (
    ResumabilityController,
    ResumeResult,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState, TERMINAL_STATES
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _make_context(state: WorkflowState = WorkflowState.DISCOVERING) -> WorkflowContext:
    now = _now()
    return WorkflowContext(
        session_id="sess_abcd1234",
        workflow_id="wf_abcd1234",
        current_state=state,
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="plumbing", location="Austin, TX"),
        timestamps=WorkflowTimestamps(created_at=now, updated_at=now, state_entered_at=now),
    )


def _save_checkpoint(
    ci: CheckpointInterface,
    state: WorkflowState = WorkflowState.DISCOVERING,
    schema_version: str = CURRENT_SCHEMA_VERSION,
    version: int = 1,
) -> None:
    ctx = _make_context(state=state)
    cp = WorkflowCheckpoint(
        schema_version=schema_version,
        checkpoint_version=version,
        session_id=ctx.session_id,
        workflow_id=ctx.workflow_id,
        context_snapshot=ctx,
        audit_trail_snapshot=[],
        saved_at=_now(),
    )
    ci.save(cp)


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestResumabilityNonTerminal:
    def test_resumes_from_discovering(self):
        ci = CheckpointInterface()
        _save_checkpoint(ci, state=WorkflowState.DISCOVERING)
        rc = ResumabilityController(ci)
        result = rc.resume("sess_abcd1234")
        assert result.resumed is True
        assert result.from_state == WorkflowState.DISCOVERING
        assert result.checkpoint is not None
        assert result.denial_reason is None

    def test_resumes_from_auditing(self):
        ci = CheckpointInterface()
        _save_checkpoint(ci, state=WorkflowState.AUDITING)
        rc = ResumabilityController(ci)
        result = rc.resume("sess_abcd1234")
        assert result.resumed is True
        assert result.from_state == WorkflowState.AUDITING


class TestResumabilityTerminalStates:
    @pytest.mark.parametrize("terminal_state", list(TERMINAL_STATES))
    def test_terminal_state_not_resumed(self, terminal_state: WorkflowState):
        ci = CheckpointInterface()
        _save_checkpoint(ci, state=terminal_state)
        rc = ResumabilityController(ci)
        result = rc.resume("sess_abcd1234")
        assert result.resumed is False
        assert result.denial_reason == "terminal_state"
        assert result.checkpoint is not None  # checkpoint is returned for inspection
        assert result.from_state == terminal_state


class TestResumabilityNoCheckpoint:
    def test_no_checkpoint_returns_false(self):
        ci = CheckpointInterface()
        rc = ResumabilityController(ci)
        result = rc.resume("sess_nonexistent")
        assert result.resumed is False
        assert result.denial_reason == "no_checkpoint_found"
        assert result.checkpoint is None


class TestResumabilitySchemaVersion:
    def test_mismatched_schema_version_not_resumed(self):
        ci = CheckpointInterface()
        _save_checkpoint(ci, schema_version="3.0")  # Old version
        rc = ResumabilityController(ci)
        result = rc.resume("sess_abcd1234")
        assert result.resumed is False
        assert result.denial_reason == "schema_version_mismatch"

    def test_current_schema_version_resumes(self):
        ci = CheckpointInterface()
        _save_checkpoint(ci, schema_version=CURRENT_SCHEMA_VERSION)
        rc = ResumabilityController(ci)
        result = rc.resume("sess_abcd1234")
        assert result.resumed is True


class TestCanResumeMirrorsResume:
    def test_can_resume_same_as_resume(self):
        ci = CheckpointInterface()
        _save_checkpoint(ci, state=WorkflowState.AUDITING)
        rc = ResumabilityController(ci)
        can = rc.can_resume("sess_abcd1234")
        will = rc.resume("sess_abcd1234")
        assert can.resumed == will.resumed
        assert can.from_state == will.from_state
        assert can.denial_reason == will.denial_reason


class TestResumeResult:
    def test_resumed_true_has_checkpoint(self):
        ci = CheckpointInterface()
        _save_checkpoint(ci, state=WorkflowState.REPORT_GENERATION)
        rc = ResumabilityController(ci)
        result = rc.resume("sess_abcd1234")
        assert result.resumed is True
        assert result.checkpoint is not None
        assert result.checkpoint.context_snapshot.current_state == WorkflowState.REPORT_GENERATION
