# tests/orchestrator_tests/test_checkpoint.py
"""
Tests: WorkflowCheckpoint and CheckpointInterface.

Validates:
  - WorkflowCheckpoint contains schema_version, workflow_version, checkpoint_version
  - save() + load() round-trip preserves all fields
  - checkpoint_version must be monotonically increasing (CheckpointVersionConflictError)
  - load() on missing session raises CheckpointNotFoundError
  - load_version() for specific version works
  - list_versions() returns sorted version list
  - next_version() returns 1 for new session, N+1 for existing
  - CheckpointInterface.build() factory produces correct checkpoint
"""
import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.interfaces.checkpoint import (
    CheckpointInterface,
    WorkflowCheckpoint,
    CURRENT_SCHEMA_VERSION,
    WORKFLOW_VERSION,
)
from agents.orchestrator_agent.exceptions import (
    CheckpointNotFoundError,
    CheckpointVersionConflictError,
)
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _make_context(state: WorkflowState = WorkflowState.IDLE) -> WorkflowContext:
    now = _now()
    return WorkflowContext(
        session_id="sess_abcd1234",
        workflow_id="wf_abcd1234",
        current_state=state,
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="plumbing", location="Austin, TX"),
        timestamps=WorkflowTimestamps(created_at=now, updated_at=now, state_entered_at=now),
    )


def _make_checkpoint(version: int = 1, context: WorkflowContext = None) -> WorkflowCheckpoint:
    ctx = context or _make_context()
    return WorkflowCheckpoint(
        checkpoint_version=version,
        session_id=ctx.session_id,
        workflow_id=ctx.workflow_id,
        context_snapshot=ctx,
        audit_trail_snapshot=[],
        saved_at=_now(),
    )


# ─── WorkflowCheckpoint model tests ──────────────────────────────────────────

class TestWorkflowCheckpointModel:
    def test_schema_version_default(self):
        cp = _make_checkpoint()
        assert cp.schema_version == CURRENT_SCHEMA_VERSION

    def test_workflow_version_default(self):
        cp = _make_checkpoint()
        assert cp.workflow_version == WORKFLOW_VERSION

    def test_checkpoint_version_must_be_positive(self):
        with pytest.raises(Exception):
            _make_checkpoint(version=0)

    def test_checkpoint_is_frozen(self):
        cp = _make_checkpoint()
        with pytest.raises(Exception):
            cp.checkpoint_version = 999  # type: ignore


class TestCheckpointInterfaceSaveLoad:
    def test_save_and_load_round_trip(self):
        ci = CheckpointInterface()
        cp = _make_checkpoint(version=1)
        ci.save(cp)
        restored = ci.load("sess_abcd1234")
        assert restored.checkpoint_version == 1
        assert restored.session_id == cp.session_id
        assert restored.context_snapshot.current_state == WorkflowState.IDLE

    def test_load_returns_latest_version(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1))
        ci.save(_make_checkpoint(version=2))
        ci.save(_make_checkpoint(version=3))
        loaded = ci.load("sess_abcd1234")
        assert loaded.checkpoint_version == 3

    def test_load_missing_session_raises(self):
        ci = CheckpointInterface()
        with pytest.raises(CheckpointNotFoundError):
            ci.load("sess_nonexistent")


class TestCheckpointVersionConflict:
    def test_non_monotonic_version_raises(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=2))
        with pytest.raises(CheckpointVersionConflictError):
            ci.save(_make_checkpoint(version=1))  # 1 <= 2

    def test_same_version_raises(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1))
        with pytest.raises(CheckpointVersionConflictError):
            ci.save(_make_checkpoint(version=1))  # same version

    def test_strictly_increasing_passes(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1))
        ci.save(_make_checkpoint(version=2))
        ci.save(_make_checkpoint(version=3))
        assert ci.list_versions("sess_abcd1234") == [1, 2, 3]


class TestCheckpointVersionManagement:
    def test_list_versions_sorted(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1))
        ci.save(_make_checkpoint(version=2))
        ci.save(_make_checkpoint(version=3))
        assert ci.list_versions("sess_abcd1234") == [1, 2, 3]

    def test_list_versions_empty_for_new_session(self):
        ci = CheckpointInterface()
        assert ci.list_versions("sess_new00000") == []

    def test_next_version_is_1_for_new_session(self):
        ci = CheckpointInterface()
        assert ci.next_version("sess_abcd1234") == 1

    def test_next_version_increments(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1))
        ci.save(_make_checkpoint(version=2))
        assert ci.next_version("sess_abcd1234") == 3

    def test_load_specific_version(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1, context=_make_context(WorkflowState.IDLE)))
        ci.save(_make_checkpoint(version=2, context=_make_context(WorkflowState.DISCOVERING)))
        v1 = ci.load_version("sess_abcd1234", 1)
        v2 = ci.load_version("sess_abcd1234", 2)
        assert v1.context_snapshot.current_state == WorkflowState.IDLE
        assert v2.context_snapshot.current_state == WorkflowState.DISCOVERING

    def test_load_missing_version_raises(self):
        ci = CheckpointInterface()
        ci.save(_make_checkpoint(version=1))
        with pytest.raises(CheckpointNotFoundError):
            ci.load_version("sess_abcd1234", 999)


class TestCheckpointBuildFactory:
    def test_build_creates_valid_checkpoint(self):
        ctx = _make_context()
        cp = CheckpointInterface.build(context=ctx, audit_trail=[], checkpoint_version=1)
        assert cp.checkpoint_version == 1
        assert cp.session_id == ctx.session_id
        assert cp.schema_version == CURRENT_SCHEMA_VERSION
        assert cp.workflow_version == WORKFLOW_VERSION
        assert cp.context_snapshot.current_state == WorkflowState.IDLE
