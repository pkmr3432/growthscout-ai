# tests/orchestrator_tests/test_validation_sprint524.py
"""
Tests for Sprint 5.2.4 — Worker Runtime Validation.
"""
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from pydantic import BaseModel

from agents.orchestrator_agent.exceptions import SchemaValidationError, BusinessValidationError
from agents.orchestrator_agent.validators.common import ValidationResult
from agents.orchestrator_agent.validators.schema_validator import SchemaValidator
from agents.orchestrator_agent.validators.discovery_validator import DiscoveryValidator
from agents.orchestrator_agent.validators.website_validator import WebsiteValidator
from agents.orchestrator_agent.validators.opportunity_validator import OpportunityValidator
from agents.orchestrator_agent.validators.report_validator import ReportValidator
from agents.orchestrator_agent.validators import ValidationPipeline

from agents.shared.schemas import (
    DiscoveryLeadsSchema,
    DiscoveryLead,
    AuditResultsSchema,
    AuditResults,
    AuditSeoData,
    OpportunityAnalysisSchema,
    CompetitorProfile,
    OpportunityImpact,
    CategoryScores,
    GrowthReportsSchema,
)
from agents.orchestrator_agent.state_machine.workflow_context import WorkflowContext, WorkflowMetadata, ExecutionMetadata, WorkflowTimestamps
from agents.orchestrator_agent.state_machine.states import WorkflowState
from agents.orchestrator_agent.hooks.audit_trail import AuditEventType
from agents.orchestrator_agent.agent import OrchestratorDependencies, GrowthScoutOrchestrator


# ─── Test Helpers ─────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _base_ctx() -> WorkflowContext:
    now = _now()
    return WorkflowContext(
        session_id="sess_11112222",
        workflow_id="wf_11112222",
        current_state=WorkflowState.IDLE,
        discovery_results=None,
        audit_results=[],
        opportunity_results=None,
        growth_report=None,
        execution_metadata=ExecutionMetadata(correlation_id="corr-001"),
        workflow_metadata=WorkflowMetadata(niche="dentist", location="Dallas, TX"),
        timestamps=WorkflowTimestamps(created_at=now, updated_at=now, state_entered_at=now),
    )


# ─── Unit Tests: SchemaValidator ──────────────────────────────────────────────

def test_schema_validator_valid_basemodel():
    schema = DiscoveryLeadsSchema(leads=[], competitor_candidates=[])
    res = SchemaValidator().validate(schema, DiscoveryLeadsSchema)
    assert res.valid is True
    assert res.normalized_output == schema


def test_schema_validator_valid_dict():
    data = {"leads": [], "competitor_candidates": []}
    res = SchemaValidator().validate(data, DiscoveryLeadsSchema)
    assert res.valid is True
    assert isinstance(res.normalized_output, DiscoveryLeadsSchema)


def test_schema_validator_valid_json_string():
    json_str = '{"leads": [], "competitor_candidates": []}'
    res = SchemaValidator().validate(json_str, DiscoveryLeadsSchema)
    assert res.valid is True
    assert isinstance(res.normalized_output, DiscoveryLeadsSchema)


def test_schema_validator_invalid_json():
    json_str = '{"leads": [], "competitor_candidates":'
    res = SchemaValidator().validate(json_str, DiscoveryLeadsSchema)
    assert res.valid is False
    assert any("JSON" in e or "balanced" in e for e in res.errors)


def test_schema_validator_missing_fields():
    data = {"leads": []}  # Missing competitor_candidates
    res = SchemaValidator().validate(data, DiscoveryLeadsSchema)
    assert res.valid is False
    assert any("competitor_candidates" in e for e in res.errors)


# ─── Unit Tests: DiscoveryValidator ───────────────────────────────────────────

def test_discovery_validator_valid():
    lead = DiscoveryLead(
        business_name="Dallas Dental",
        address="Dallas, TX",
        website_url="https://dallasdental.com",
        website_status="Modern Website"
    )
    schema = DiscoveryLeadsSchema(leads=[lead], competitor_candidates=[])
    res = DiscoveryValidator().validate(schema, DiscoveryLeadsSchema)
    assert res.valid is True
    assert res.normalized_output.leads[0].business_name == "Dallas Dental"
    assert res.normalized_output.leads[0].website_url == "https://dallasdental.com"


def test_discovery_validator_duplicate_business():
    lead = DiscoveryLead(
        business_name=" Dallas Dental ",
        address="Dallas, TX",
        website_url="https://dallasdental.com",
        website_status="Modern Website"
    )
    schema = DiscoveryLeadsSchema(leads=[lead, lead], competitor_candidates=[])
    res = DiscoveryValidator().validate(schema, DiscoveryLeadsSchema)
    assert res.valid is False
    assert any("Duplicate business name" in e for e in res.errors)


def test_discovery_validator_duplicate_url():
    lead1 = DiscoveryLead(
        business_name="Dallas Dental 1",
        address="Dallas, TX",
        website_url="https://dallasdental.com/",
        website_status="Modern Website"
    )
    lead2 = DiscoveryLead(
        business_name="Dallas Dental 2",
        address="Dallas, TX",
        website_url="https://dallasdental.com",
        website_status="Modern Website"
    )
    schema = DiscoveryLeadsSchema(leads=[lead1, lead2], competitor_candidates=[])
    res = DiscoveryValidator().validate(schema, DiscoveryLeadsSchema)
    assert res.valid is False
    assert any("Duplicate website URL" in e for e in res.errors)


def test_discovery_validator_normalization_idempotent():
    lead = DiscoveryLead(
        business_name=" Dallas Dental ",
        address=" Dallas, TX ",
        website_url="HTTPS://DallasDental.com/",
        website_status="Modern Website"
    )
    schema = DiscoveryLeadsSchema(leads=[lead], competitor_candidates=[])
    
    # First normalization
    res1 = DiscoveryValidator().validate(schema, DiscoveryLeadsSchema)
    assert res1.valid is True
    norm1 = res1.normalized_output
    assert norm1.leads[0].business_name == "Dallas Dental"
    assert norm1.leads[0].address == "Dallas, TX"
    assert norm1.leads[0].website_url == "https://dallasdental.com"

    # Second normalization (should yield the same result)
    res2 = DiscoveryValidator().validate(norm1, DiscoveryLeadsSchema)
    assert res2.valid is True
    assert res2.normalized_output == norm1


# ─── Unit Tests: WebsiteValidator ─────────────────────────────────────────────

def test_website_validator_valid():
    seo = AuditSeoData(meta_title=" Dallas Dentist ", meta_description="Desc", h1_elements=["Dallas Dentist"], has_schema_markup=True)
    audit = AuditResults(
        website_url="https://dallasdental.com",
        http_status_code=200,
        cms=" WordPress ",
        load_time_seconds=1.5,
        has_booking_widget=False,
        seo_data=seo
    )
    schema = AuditResultsSchema(audit_results=audit)
    res = WebsiteValidator().validate(schema, AuditResultsSchema)
    assert res.valid is True
    assert res.normalized_output.audit_results.cms == "wordpress"
    assert res.normalized_output.audit_results.seo_data.meta_title == "Dallas Dentist"


def test_website_validator_invalid_http_code():
    seo = AuditSeoData(meta_title="Dallas Dentist", has_schema_markup=True)
    audit = AuditResults(
        website_url="https://dallasdental.com",
        http_status_code=99,
        cms="wordpress",
        load_time_seconds=1.5,
        has_booking_widget=False,
        seo_data=seo
    )
    schema = AuditResultsSchema(audit_results=audit)
    res = WebsiteValidator().validate(schema, AuditResultsSchema)
    assert res.valid is False
    assert any("HTTP status code" in e for e in res.errors)


def test_website_validator_negative_load_time():
    seo = AuditSeoData(meta_title="Dallas Dentist", has_schema_markup=True)
    audit = AuditResults(
        website_url="https://dallasdental.com",
        http_status_code=200,
        cms="wordpress",
        load_time_seconds=-0.5,
        has_booking_widget=False,
        seo_data=seo
    )
    schema = AuditResultsSchema(audit_results=audit)
    res = WebsiteValidator().validate(schema, AuditResultsSchema)
    assert res.valid is False
    assert any("Load time" in e for e in res.errors)


# ─── Unit Tests: OpportunityValidator ─────────────────────────────────────────

def test_opportunity_validator_valid():
    scores = CategoryScores(no_website=10, seo=80, analytics=100)
    schema = OpportunityAnalysisSchema(
        opportunities=["SEO Optimization"],
        lead_score=75,
        competitor_profiles=[
            CompetitorProfile(business_name="Comp A", website_url="https://compa.com", google_rating=4.5, review_count=20),
            CompetitorProfile(business_name="Comp B", website_url="https://compb.com", google_rating=4.8, review_count=50)
        ],
        opportunity_scores=scores,
        business_impact_analysis=[
            OpportunityImpact(technical_finding="Slow load", business_consequence="High bounce")
        ],
        opportunity_summary="Overall good"
    )
    res = OpportunityValidator().validate(schema, OpportunityAnalysisSchema)
    assert res.valid is True
    # Sorting of competitors should be by review_count DESC, then google_rating DESC
    assert res.normalized_output.competitor_profiles[0].business_name == "Comp B"
    assert res.normalized_output.competitor_profiles[1].business_name == "Comp A"


def test_opportunity_validator_invalid_lead_score():
    scores = CategoryScores(seo=80)
    schema = OpportunityAnalysisSchema(
        opportunities=["SEO"],
        lead_score=105, # Out of range
        competitor_profiles=[],
        opportunity_scores=scores,
        business_impact_analysis=[OpportunityImpact(technical_finding="F", business_consequence="C")],
        opportunity_summary="S"
    )
    res = OpportunityValidator().validate(schema, OpportunityAnalysisSchema)
    assert res.valid is False
    assert any("lead_score" in e for e in res.errors)


def test_opportunity_validator_invalid_category_score():
    scores = CategoryScores(seo=-5) # Out of range
    schema = OpportunityAnalysisSchema(
        opportunities=["SEO"],
        lead_score=75,
        competitor_profiles=[],
        opportunity_scores=scores,
        business_impact_analysis=[OpportunityImpact(technical_finding="F", business_consequence="C")],
        opportunity_summary="S"
    )
    res = OpportunityValidator().validate(schema, OpportunityAnalysisSchema)
    assert res.valid is False
    assert any("Category score 'seo'" in e for e in res.errors)


def test_opportunity_validator_duplicate_competitor():
    scores = CategoryScores(seo=80)
    comp = CompetitorProfile(business_name="Comp A", website_url="https://compa.com")
    schema = OpportunityAnalysisSchema(
        opportunities=["SEO"],
        lead_score=75,
        competitor_profiles=[comp, comp], # Duplicate
        opportunity_scores=scores,
        business_impact_analysis=[OpportunityImpact(technical_finding="F", business_consequence="C")],
        opportunity_summary="S"
    )
    res = OpportunityValidator().validate(schema, OpportunityAnalysisSchema)
    assert res.valid is False
    assert any("Duplicate competitor profile name" in e for e in res.errors)


# ─── Unit Tests: ReportValidator ──────────────────────────────────────────────

def test_report_validator_valid():
    schema = GrowthReportsSchema(
        growth_report_markdown="# Dallas Dentist Report\nThis report is long enough to satisfy character constraints.",
        email_draft="Draft...",
        proposal_markdown="Proposal..."
    )
    res = ReportValidator().validate(schema, GrowthReportsSchema)
    assert res.valid is True


def test_report_validator_too_short():
    schema = GrowthReportsSchema(
        growth_report_markdown="Short report", # Less than 50 chars
    )
    res = ReportValidator().validate(schema, GrowthReportsSchema)
    assert res.valid is False
    assert any("too short" in e for e in res.errors)


# ─── Unit Tests: ValidationPipeline ───────────────────────────────────────────

def test_validation_pipeline_metrics():
    vp = ValidationPipeline()
    schema = DiscoveryLeadsSchema(leads=[], competitor_candidates=[])
    res = vp.validate("business_discovery_agent", schema, DiscoveryLeadsSchema)
    assert res.valid is True
    assert "validation_duration_ms" in res.metrics
    assert res.metrics["validator_name"] == "DiscoveryValidator"
    assert res.metrics["worker_name"] == "business_discovery_agent"
    assert res.metrics["normalized"] is True
    assert res.metrics["failure_type"] is None


def test_validation_pipeline_serialization():
    vp = ValidationPipeline()
    schema = DiscoveryLeadsSchema(leads=[], competitor_candidates=[])
    res = vp.validate("business_discovery_agent", schema, DiscoveryLeadsSchema)
    
    # Test Pydantic model serialization of ValidationResult
    serialized = res.model_dump_json()
    assert '"valid":true' in serialized
    assert '"evidence_summary"' in serialized


# ─── Integration Tests: WorkflowExecutor & Orchestrator ───────────────────────

class DummyInput(BaseModel):
    niche: str = "dentist"
    location: str = "Dallas, TX"


@pytest.mark.asyncio
async def test_workflow_executor_validation_success():
    # Setup orchestrator and mock execution
    deps = OrchestratorDependencies()
    orchestrator = GrowthScoutOrchestrator(deps)
    executor = orchestrator._executor

    context = _base_ctx()
    lead = DiscoveryLead(
        business_name="Austin Dental",
        address="Austin, TX",
        website_status="No Website"
    )
    valid_output = DiscoveryLeadsSchema(leads=[lead], competitor_candidates=[])

    async def mock_execute_agent_run(agent_instance, request, output_schema):
        return valid_output

    executor._execute_agent_run = mock_execute_agent_run

    # Invoke worker
    res = await executor._invoke_worker_with_retry(
        context, "business_discovery_agent", DummyInput(), DiscoveryLeadsSchema
    )
    assert res.success is True
    assert isinstance(res.output, DiscoveryLeadsSchema)

    # Check metrics
    metrics = deps.metrics_collector.get_metrics(context.session_id)
    assert metrics["validation_runs_total"] == 1
    assert metrics["validation_failures_total"] == 0
    assert metrics["normalized_outputs_total"] == 1

    # Check audit trail
    trail = deps.audit_writer.read_trail(context.session_id)
    event_types = [entry.event_type for entry in trail]
    assert AuditEventType.VALIDATION_STARTED in event_types
    assert AuditEventType.OUTPUT_NORMALIZED in event_types
    assert AuditEventType.VALIDATION_SUCCEEDED in event_types


@pytest.mark.asyncio
async def test_workflow_executor_schema_validation_failure_and_retry():
    # Setup orchestrator with retry configuration
    deps = OrchestratorDependencies()
    orchestrator = GrowthScoutOrchestrator(deps)
    executor = orchestrator._executor

    context = _base_ctx()
    # Invalid raw string that will fail parsing
    invalid_raw_str = "{invalid_json"

    attempts = 0

    async def mock_execute_agent_run(agent_instance, request, output_schema):
        nonlocal attempts
        attempts += 1
        return invalid_raw_str

    executor._execute_agent_run = mock_execute_agent_run

    # Invoke worker (should fail immediately without retries)
    res = await executor._invoke_worker_with_retry(
        context, "business_discovery_agent", DummyInput(), DiscoveryLeadsSchema
    )
    assert res.success is False
    assert attempts == 1  # No retries!

    # Check metrics
    metrics = deps.metrics_collector.get_metrics(context.session_id)
    assert metrics["validation_runs_total"] == 1
    assert metrics["validation_failures_total"] == 1
    assert metrics["schema_failures_total"] == 1

    # Check audit trail has SCHEMA_VALIDATION_FAILED
    trail = deps.audit_writer.read_trail(context.session_id)
    event_types = [entry.event_type for entry in trail]
    assert AuditEventType.SCHEMA_VALIDATION_FAILED in event_types


@pytest.mark.asyncio
async def test_workflow_executor_business_validation_fail_fast():
    # Setup orchestrator
    deps = OrchestratorDependencies()
    orchestrator = GrowthScoutOrchestrator(deps)
    executor = orchestrator._executor

    context = _base_ctx()
    # Output has duplicate business names which fails business validation
    lead = DiscoveryLead(business_name="Austin Dental", address="Austin, TX", website_status="No Website")
    duplicate_output = DiscoveryLeadsSchema(leads=[lead, lead], competitor_candidates=[])

    attempts = 0

    async def mock_execute_agent_run(agent_instance, request, output_schema):
        nonlocal attempts
        attempts += 1
        return duplicate_output

    executor._execute_agent_run = mock_execute_agent_run

    # Invoke worker
    res = await executor._invoke_worker_with_retry(
        context, "business_discovery_agent", DummyInput(), DiscoveryLeadsSchema
    )
    # Business validation failure is non-retryable, should fail immediately
    assert res.success is False
    assert attempts == 1  # No retries!

    # Check metrics
    metrics = deps.metrics_collector.get_metrics(context.session_id)
    assert metrics["validation_runs_total"] == 1
    assert metrics["validation_failures_total"] == 1
    assert metrics["business_failures_total"] == 1

    # Check audit trail has BUSINESS_VALIDATION_FAILED
    trail = deps.audit_writer.read_trail(context.session_id)
    event_types = [entry.event_type for entry in trail]
    assert AuditEventType.BUSINESS_VALIDATION_FAILED in event_types
