# tests/orchestrator_tests/test_workflow_context.py
"""
Tests: WorkflowContext canonical runtime model.

Validates:
  - Field defaults and required field enforcement
  - session_id and workflow_id pattern validation
  - PartitionSummary integrity check
  - WorkflowTimestamps chronology check
  - Immutable factory helpers (with_state, with_discovery, etc.)
  - JSON round-trip serialization
"""
import pytest
from datetime import datetime, timezone, timedelta

from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
    PartitionSummary,
    EvidenceReference,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_timestamps(**overrides) -> WorkflowTimestamps:
    now = _now()
    return WorkflowTimestamps(
        created_at=overrides.get("created_at", now),
        updated_at=overrides.get("updated_at", now),
        state_entered_at=overrides.get("state_entered_at", now),
        estimated_deadline=overrides.get("estimated_deadline", None),
    )


def _make_context(**overrides) -> WorkflowContext:
    """Build a minimal valid WorkflowContext for testing."""
    now = _now()
    return WorkflowContext(
        session_id=overrides.get("session_id", "sess_abcd1234"),
        workflow_id=overrides.get("workflow_id", "wf_abcd1234"),
        current_state=overrides.get("current_state", WorkflowState.IDLE),
        execution_metadata=overrides.get("execution_metadata", ExecutionMetadata(
            correlation_id="corr-test-001"
        )),
        workflow_metadata=overrides.get("workflow_metadata", WorkflowMetadata(
            niche="HVAC repair",
            location="Austin, TX",
        )),
        timestamps=overrides.get("timestamps", _make_timestamps()),
    )


# ─── session_id validation ────────────────────────────────────────────────────

class TestSessionIdValidation:
    def test_valid_session_id(self):
        ctx = _make_context(session_id="sess_a1b2c3d4")
        assert ctx.session_id == "sess_a1b2c3d4"

    def test_invalid_session_id_no_prefix(self):
        with pytest.raises(Exception):
            _make_context(session_id="a1b2c3d4")

    def test_invalid_session_id_wrong_length(self):
        with pytest.raises(Exception):
            _make_context(session_id="sess_abc")

    def test_invalid_session_id_uppercase(self):
        with pytest.raises(Exception):
            _make_context(session_id="sess_ABCD1234")


# ─── workflow_id validation ───────────────────────────────────────────────────

class TestWorkflowIdValidation:
    def test_valid_workflow_id(self):
        ctx = _make_context(workflow_id="wf_deadbeef")
        assert ctx.workflow_id == "wf_deadbeef"

    def test_invalid_workflow_id(self):
        with pytest.raises(Exception):
            _make_context(workflow_id="workflow_abc12345")


# ─── Default values ───────────────────────────────────────────────────────────

class TestWorkflowContextDefaults:
    def test_default_state_is_idle(self):
        ctx = _make_context()
        assert ctx.current_state == WorkflowState.IDLE

    def test_default_audit_results_empty(self):
        ctx = _make_context()
        assert ctx.audit_results == []

    def test_default_evidence_references_empty(self):
        ctx = _make_context()
        assert ctx.evidence_references == []

    def test_default_revision_count_zero(self):
        ctx = _make_context()
        assert ctx.revision_count == 0

    def test_default_discovery_results_none(self):
        ctx = _make_context()
        assert ctx.discovery_results is None

    def test_default_growth_report_none(self):
        ctx = _make_context()
        assert ctx.growth_report is None

    def test_revision_count_max_enforced(self):
        with pytest.raises(Exception):
            _make_context().__class__.model_validate({
                **_make_context().model_dump(),
                "revision_count": 6,
            })


# ─── Immutability via factory helpers ────────────────────────────────────────

class TestWorkflowContextImmutability:
    def test_with_state_returns_new_instance(self):
        ctx = _make_context()
        new_ctx = ctx.with_state(WorkflowState.DISCOVERING, _now())
        assert new_ctx is not ctx
        assert new_ctx.current_state == WorkflowState.DISCOVERING
        assert ctx.current_state == WorkflowState.IDLE  # Original unchanged

    def test_with_discovery_returns_new_instance(self):
        from agents.shared.schemas import DiscoveryLeadsSchema
        ctx = _make_context()
        schema = DiscoveryLeadsSchema(leads=[], competitor_candidates=[])
        new_ctx = ctx.with_discovery(schema, _now())
        assert new_ctx is not ctx
        assert new_ctx.discovery_results is schema
        assert ctx.discovery_results is None

    def test_with_incremented_revision_returns_new_instance(self):
        ctx = _make_context()
        new_ctx = ctx.with_incremented_revision(_now())
        assert new_ctx.revision_count == 1
        assert ctx.revision_count == 0

    def test_with_audit_appends_not_replaces(self):
        from agents.shared.schemas import AuditResultsSchema, AuditResults, AuditSeoData
        ctx = _make_context()
        audit = AuditResultsSchema(
            audit_results=AuditResults(
                website_url="https://example.com",
                http_status_code=200,
                cms="wordpress",
                load_time_seconds=1.2,
                has_booking_widget=False,
                seo_data=AuditSeoData(has_schema_markup=False),
            )
        )
        ctx2 = ctx.with_audit(audit, _now())
        ctx3 = ctx2.with_audit(audit, _now())
        assert len(ctx3.audit_results) == 2
        assert len(ctx2.audit_results) == 1
        assert len(ctx.audit_results) == 0


# ─── PartitionSummary integrity ───────────────────────────────────────────────

class TestPartitionSummary:
    def test_valid_partition_summary(self):
        ps = PartitionSummary(
            total_leads=5,
            website_leads=3,
            no_website_leads=2,
            integrity_valid=True,
        )
        assert ps.integrity_valid is True

    def test_invalid_integrity_flag_raises(self):
        with pytest.raises(Exception):
            PartitionSummary(
                total_leads=5,
                website_leads=3,
                no_website_leads=1,  # 3+1=4 != 5
                integrity_valid=True,
            )

    def test_integrity_false_skips_check(self):
        ps = PartitionSummary(
            total_leads=5,
            website_leads=3,
            no_website_leads=1,
            integrity_valid=False,  # no assertion when False
        )
        assert ps.integrity_valid is False


# ─── WorkflowTimestamps chronology ───────────────────────────────────────────

class TestWorkflowTimestamps:
    def test_updated_at_before_created_at_raises(self):
        now = _now()
        with pytest.raises(Exception):
            WorkflowTimestamps(
                created_at=now,
                updated_at=now - timedelta(seconds=1),  # before created_at
                state_entered_at=now,
            )

    def test_equal_timestamps_accepted(self):
        now = _now()
        ts = WorkflowTimestamps(
            created_at=now, updated_at=now, state_entered_at=now
        )
        assert ts.created_at == ts.updated_at


# ─── JSON round-trip ──────────────────────────────────────────────────────────

class TestWorkflowContextSerialization:
    def test_json_round_trip(self):
        ctx = _make_context()
        json_str = ctx.model_dump_json()
        restored = WorkflowContext.model_validate_json(json_str)
        assert restored.session_id == ctx.session_id
        assert restored.workflow_id == ctx.workflow_id
        assert restored.current_state == ctx.current_state
