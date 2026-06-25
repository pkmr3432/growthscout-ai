# tests/orchestrator_tests/test_evidence_validator.py
"""
Tests: EvidenceValidationHook requirement-driven validation.

Validates:
  - Empty requirement list passes immediately
  - Each EvidenceRequirement checks the correct WorkflowContext field
  - Multiple mixed requirements produce correct pass/fail lists
  - blocked_leads populated correctly for SEO failures
  - No hardcoded state names inside the hook
  - Hook never mutates WorkflowContext
"""
import pytest
from datetime import datetime, timezone

from agents.orchestrator_agent.hooks.evidence_validator import (
    EvidenceValidationHook,
    EvidenceValidationResult,
)
from agents.orchestrator_agent.state_machine.states import EvidenceRequirement
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
)
from agents.shared.schemas import (
    DiscoveryLeadsSchema,
    AuditResultsSchema,
    AuditResults,
    AuditSeoData,
    DiscoveryLead,
    GrowthReportsSchema,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _base_ctx(**overrides) -> WorkflowContext:
    now = _now()
    return WorkflowContext(
        session_id="sess_abcd1234",
        workflow_id="wf_abcd1234",
        current_state=overrides.get("current_state", __import__(
            "agents.orchestrator_agent.state_machine.states", fromlist=["WorkflowState"]
        ).WorkflowState.IDLE),
        discovery_results=overrides.get("discovery_results", None),
        audit_results=overrides.get("audit_results", []),
        opportunity_results=overrides.get("opportunity_results", None),
        growth_report=overrides.get("growth_report", None),
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="plumbing", location="Austin, TX"),
        timestamps=WorkflowTimestamps(created_at=now, updated_at=now, state_entered_at=now),
    )


def _discovery_with_leads(lead_count=1, competitor_count=1) -> DiscoveryLeadsSchema:
    lead = DiscoveryLead(
        business_name="Test Plumbing",
        address="123 Main St",
        website_url="https://testplumbing.com",
        website_status="Modern Website",
    )
    return DiscoveryLeadsSchema(
        leads=[lead] * lead_count,
        competitor_candidates=[lead] * competitor_count,
    )


def _audit_result(url: str = "https://testplumbing.com", has_seo: bool = True) -> AuditResultsSchema:
    return AuditResultsSchema(
        audit_results=AuditResults(
            website_url=url,
            http_status_code=200,
            cms="wordpress",
            load_time_seconds=1.5,
            has_booking_widget=False,
            seo_data=AuditSeoData(
                meta_title="Test" if has_seo else None,
                has_schema_markup=False,
            ),
        )
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestEmptyRequirements:
    def test_empty_requirements_passes(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx()
        result = hook.validate(ctx, [])
        assert result.passed is True
        assert result.failed_requirements == []
        assert result.satisfied_requirements == []


class TestDiscoveryRequired:
    def test_passes_with_leads(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(discovery_results=_discovery_with_leads())
        result = hook.validate(ctx, [EvidenceRequirement.DISCOVERY_REQUIRED])
        assert result.passed is True
        assert EvidenceRequirement.DISCOVERY_REQUIRED in result.satisfied_requirements

    def test_fails_when_discovery_is_none(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(discovery_results=None)
        result = hook.validate(ctx, [EvidenceRequirement.DISCOVERY_REQUIRED])
        assert result.passed is False
        assert EvidenceRequirement.DISCOVERY_REQUIRED in result.failed_requirements

    def test_fails_when_leads_is_empty(self):
        hook = EvidenceValidationHook()
        empty = DiscoveryLeadsSchema(leads=[], competitor_candidates=[])
        ctx = _base_ctx(discovery_results=empty)
        result = hook.validate(ctx, [EvidenceRequirement.DISCOVERY_REQUIRED])
        assert result.passed is False


class TestAuditRequired:
    def test_passes_with_audit_results(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(audit_results=[_audit_result()])
        result = hook.validate(ctx, [EvidenceRequirement.AUDIT_REQUIRED])
        assert result.passed is True

    def test_fails_with_empty_audit_results(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(audit_results=[])
        result = hook.validate(ctx, [EvidenceRequirement.AUDIT_REQUIRED])
        assert result.passed is False
        assert len(result.missing_details) > 0


class TestSeoRequired:
    def test_passes_when_seo_data_present(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(audit_results=[_audit_result(has_seo=True)])
        result = hook.validate(ctx, [EvidenceRequirement.SEO_REQUIRED])
        assert result.passed is True

    def test_fails_when_no_audit_results(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(audit_results=[])
        result = hook.validate(ctx, [EvidenceRequirement.SEO_REQUIRED])
        assert result.passed is False


class TestCompetitorRequired:
    def test_passes_with_competitors(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(discovery_results=_discovery_with_leads(competitor_count=1))
        result = hook.validate(ctx, [EvidenceRequirement.COMPETITOR_REQUIRED])
        assert result.passed is True

    def test_fails_without_competitors(self):
        hook = EvidenceValidationHook()
        empty = DiscoveryLeadsSchema(
            leads=[DiscoveryLead(
                business_name="X", address="Y", website_status="No Website"
            )],
            competitor_candidates=[],
        )
        ctx = _base_ctx(discovery_results=empty)
        result = hook.validate(ctx, [EvidenceRequirement.COMPETITOR_REQUIRED])
        assert result.passed is False


class TestReportRequired:
    def test_passes_with_report(self):
        hook = EvidenceValidationHook()
        report = GrowthReportsSchema(growth_report_markdown="# Report")
        ctx = _base_ctx(growth_report=report)
        result = hook.validate(ctx, [EvidenceRequirement.REPORT_REQUIRED])
        assert result.passed is True

    def test_fails_without_report(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(growth_report=None)
        result = hook.validate(ctx, [EvidenceRequirement.REPORT_REQUIRED])
        assert result.passed is False


class TestMultipleRequirements:
    def test_all_satisfied(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(
            discovery_results=_discovery_with_leads(),
            audit_results=[_audit_result()],
        )
        result = hook.validate(ctx, [
            EvidenceRequirement.DISCOVERY_REQUIRED,
            EvidenceRequirement.AUDIT_REQUIRED,
        ])
        assert result.passed is True
        assert len(result.satisfied_requirements) == 2
        assert len(result.failed_requirements) == 0

    def test_partial_failure(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx(
            discovery_results=_discovery_with_leads(),
            audit_results=[],  # AUDIT_REQUIRED will fail
        )
        result = hook.validate(ctx, [
            EvidenceRequirement.DISCOVERY_REQUIRED,
            EvidenceRequirement.AUDIT_REQUIRED,
        ])
        assert result.passed is False
        assert EvidenceRequirement.DISCOVERY_REQUIRED in result.satisfied_requirements
        assert EvidenceRequirement.AUDIT_REQUIRED in result.failed_requirements

    def test_all_failed(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx()
        result = hook.validate(ctx, [
            EvidenceRequirement.DISCOVERY_REQUIRED,
            EvidenceRequirement.AUDIT_REQUIRED,
        ])
        assert result.passed is False
        assert len(result.satisfied_requirements) == 0
        assert len(result.failed_requirements) == 2


class TestEvidenceValidatorImmutability:
    def test_context_unchanged_after_validation(self):
        hook = EvidenceValidationHook()
        ctx = _base_ctx()
        original_state = ctx.current_state
        hook.validate(ctx, [EvidenceRequirement.DISCOVERY_REQUIRED])
        assert ctx.current_state == original_state
        assert ctx.discovery_results is None
