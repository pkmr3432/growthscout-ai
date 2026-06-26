# scratch/run_benchmarks.py
import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Type
from unittest.mock import patch, MagicMock

# Adjust path to import from workspace
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.orchestrator_agent.agent import OrchestratorDependencies, GrowthScoutOrchestrator
from agents.orchestrator_agent.workflow_executor import WorkflowExecutor, TransitionPlan
from agents.orchestrator_agent.state_machine.states import WorkflowState, TERMINAL_STATES
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
)
from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.exceptions import (
    SchemaValidationError,
    BusinessValidationError,
)
from agents.orchestrator_agent.error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from agents.orchestrator_agent.service_names import ServiceName
from agents.orchestrator_agent.hooks.audit_trail import AuditEventType
from agents.shared.schemas import (
    DiscoveryLead,
    DiscoveryLeadsSchema,
    AuditResultsSchema,
    AuditResults,
    AuditSeoData,
    OpportunityAnalysisSchema,
    CategoryScores,
    GrowthReportsSchema,
    OpportunityImpact,
    CompetitorProfile,
)

# Load dataset and expected results
DATASET_PATH = "scratch/benchmark_dataset.json"
EXPECTED_RESULTS_PATH = "scratch/benchmark_expected_results.json"
RESULTS_OUTPUT_PATH = "scratch/benchmark_results.json"

def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

# Helper generators for mock responses
def make_mock_discovery_leads(niche: str, location: str, total_leads: int, website_leads_count: int) -> DiscoveryLeadsSchema:
    leads = []
    for i in range(total_leads):
        has_web = (i < website_leads_count)
        biz_name = f"{niche} Specialist {i} of {location}"
        leads.append(DiscoveryLead(
            business_name=biz_name,
            address=f"{100 + i} Main St, {location}",
            website_url=f"http://{niche.lower()}biz{i}.com" if has_web else None,
            website_status="Modern Website" if has_web else "No Website",
            google_rating=4.5 + (i % 5) * 0.1,
            review_count=10 + i * 5,
            google_maps_place_id=f"place_lead_{i}_{niche.lower().replace(' ', '_')}"
        ))
    competitors = [
        DiscoveryLead(
            business_name=f"{niche} Competitor Top of {location}",
            address=f"200 Competitor Rd, {location}",
            website_url=f"http://{niche.lower()}topcomp.com",
            website_status="Modern Website",
            google_rating=4.9,
            review_count=150,
            google_maps_place_id=f"place_comp_{niche.lower().replace(' ', '_')}"
        )
    ]
    return DiscoveryLeadsSchema(leads=leads, competitor_candidates=competitors)

def make_mock_audit_results(url: str) -> AuditResultsSchema:
    return AuditResultsSchema(
        audit_results=AuditResults(
            website_url=url,
            http_status_code=200,
            cms="wordpress",
            load_time_seconds=1.2,
            has_booking_widget=True,
            seo_data=AuditSeoData(
                meta_title=f"Best site at {url}",
                meta_description="Consultative local business page.",
                h1_elements=["Welcome To Our Business"],
                has_schema_markup=True
            )
        )
    )

def make_mock_opportunity_results(lead_score: int = 85) -> OpportunityAnalysisSchema:
    return OpportunityAnalysisSchema(
        opportunities=["seo", "conversion_optimization"],
        lead_score=lead_score,
        competitor_profiles=[
            CompetitorProfile(
                business_name="Competitor Top",
                website_url="http://competitortop.com",
                google_rating=4.9,
                review_count=150
            )
        ],
        opportunity_scores=CategoryScores(
            no_website=0,
            website_modernization=20,
            seo=80,
            performance=50,
            conversion_optimization=90,
            analytics=40,
            reputation=30,
            competitive_positioning=70
        ),
        business_impact_analysis=[
            OpportunityImpact(
                technical_finding="Slow load time",
                business_consequence="Higher bounce rate"
            )
        ],
        opportunity_summary="Great opportunities identified."
    )

def make_mock_growth_report(niche: str, location: str) -> GrowthReportsSchema:
    return GrowthReportsSchema(
        growth_report_markdown=f"# Growth Intelligence Report for {niche} in {location}\nWe analyzed your digital presence and found great opportunities to improve lead generation. Specifically, adding a booking widget can increase conversions by up to 35%.",
        email_draft="Subject: Increase bookings at your location",
        proposal_markdown="# Business Proposal for optimization services."
    )

async def run_benchmark_case(
    case_name: str,
    case_input: dict,
    expected: dict,
    simulate_crawler_failures: bool = False,
    test_resumption: bool = False
) -> dict:
    print(f"\n==================================================")
    print(f"RUNNING BENCHMARK CASE: {case_name}")
    print(f"==================================================")

    niche = case_input["niche"]
    location = case_input["location"]
    max_leads = case_input["max_leads"]

    # Initialize configuration
    config = RuntimeConfig(
        checkpoint_backend="in_memory",
        gemini_api_key="mocked_gemini_key",
        google_maps_api_key="mocked_maps_key",
        workflow_timeout_seconds=expected["max_execution_time_seconds"],
        max_retries=2,
        backoff_factor=0.01,
        environment="development"
    )

    # Initialize orchestrator
    orchestrator = await GrowthScoutOrchestrator.initialize(config=config, bypass_preflight=True)
    executor = orchestrator._executor

    # Session and Workflow IDs
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
    now_dt = datetime.now(timezone.utc)

    # Create initial workflow context
    context = WorkflowContext(
        session_id=session_id,
        workflow_id=workflow_id,
        current_state=WorkflowState.IDLE,
        execution_metadata=ExecutionMetadata(correlation_id=f"corr-{case_name}"),
        workflow_metadata=WorkflowMetadata(niche=niche, location=location, max_leads=max_leads),
        timestamps=WorkflowTimestamps(created_at=now_dt, updated_at=now_dt, state_entered_at=now_dt)
    )

    # Setup worker mocks
    leads_count_to_discover = max_leads
    # Let's say half of discovered leads have websites, except for plumbing_seattle which has 0
    if case_name == "plumbing_seattle":
        website_leads_count = 0
    elif case_name == "hvac_austin":
        website_leads_count = 5
    else:  # dentistry_chicago
        website_leads_count = 4

    # Keep track of worker invocations
    crawler_failures_count = 0
    total_discovery_invocations = 0

    async def patched_execute_agent_run(executor_self, agent_instance, request, output_schema, session_id=None):
        nonlocal crawler_failures_count, total_discovery_invocations
        worker_name = request.worker_name

        if worker_name == "business_discovery_agent":
            total_discovery_invocations += 1
            return make_mock_discovery_leads(niche, location, leads_count_to_discover, website_leads_count)

        elif worker_name == "website_analysis_agent":
            url = request.input_payload.website_url
            if simulate_crawler_failures and crawler_failures_count < 2:
                crawler_failures_count += 1
                raise GrowthScoutRuntimeError(
                    error_code=RuntimeErrorCode.NETWORK_ERROR,
                    message=f"Simulated connection timeout fetching {url}",
                    service=ServiceName.SCRAPER,
                    retryable=False  # Do not retry to make it fail quickly
                )
            return make_mock_audit_results(url)

        elif worker_name == "opportunity_agent":
            return make_mock_opportunity_results()

        elif worker_name == "growth_intelligence_agent":
            return make_mock_growth_report(niche, location)

        raise ValueError(f"Unknown agent: {worker_name}")

    # Start timing
    start_time = time.perf_counter()

    with patch.object(WorkflowExecutor, "_execute_agent_run", patched_execute_agent_run):
        # Execute workflow until AWAITING_APPROVAL (or terminal if no leads or failed)
        final_context = await orchestrator.start_workflow(context)

        # Check for intermediate checkpoint and resumption if requested
        if test_resumption and final_context.current_state == WorkflowState.AWAITING_APPROVAL:
            print("[*] Simulating Workflow Resumption Scenario...")
            # Let's retrieve the last saved checkpoint
            checkpoint = orchestrator._ci.load(session_id)
            assert checkpoint is not None
            assert checkpoint.context_snapshot.current_state == WorkflowState.AWAITING_APPROVAL

            # Execute resumption
            success, resumed_context = orchestrator.attempt_resume(session_id)
            assert success is True
            assert resumed_context is not None
            assert resumed_context.recovery_id is not None
            assert resumed_context.current_state == WorkflowState.AWAITING_APPROVAL
            print(f"  - Recovery ID generated: {resumed_context.recovery_id}")

            # Verify that trace contains recovery events
            trace = executor.get_trace(session_id)
            resumed_trace_entries = [e for e in trace.entries if e.event_type == "execution_started" or "resumed" in e.event_type]
            print(f"  - Resumption trace entries count: {len(resumed_trace_entries)}")

            # Update final context to resumed one
            final_context = resumed_context

        # If it reached AWAITING_APPROVAL, approve report to run to COMPLETED
        if final_context.current_state == WorkflowState.AWAITING_APPROVAL:
            final_context = await orchestrator.submit_hitl_action(session_id, approved=True)

    execution_duration = time.perf_counter() - start_time
    print(f"[*] Case {case_name} finished in state {final_context.current_state.value} (duration: {execution_duration:.2f}s)")

    # Assert and verify constraints
    discovered_leads = len(final_context.discovery_results.leads) if final_context.discovery_results else 0
    websites_analyzed = len(final_context.audit_results) if final_context.audit_results else 0
    successful_reports = 1 if final_context.growth_report else 0

    assert final_context.current_state == WorkflowState.COMPLETED, f"Expected COMPLETED state, got {final_context.current_state.value}"
    assert discovered_leads >= expected["min_discovered_leads"], f"Expected >= {expected['min_discovered_leads']} leads, got {discovered_leads}"
    assert websites_analyzed >= expected["min_websites_analyzed"], f"Expected >= {expected['min_websites_analyzed']} website audits, got {websites_analyzed}"
    assert successful_reports >= expected["min_successful_reports"], f"Expected >= {expected['min_successful_reports']} growth reports, got {successful_reports}"
    assert execution_duration <= expected["max_execution_time_seconds"], f"Expected duration <= {expected['max_execution_time_seconds']}s, got {execution_duration:.2f}s"

    print(f"[+] Constraints verified for {case_name}:")
    print(f"  - Discovered leads: {discovered_leads} (Expected >= {expected['min_discovered_leads']})")
    print(f"  - Websites analyzed: {websites_analyzed} (Expected >= {expected['min_websites_analyzed']})")
    print(f"  - Successful reports: {successful_reports} (Expected >= {expected['min_successful_reports']})")
    print(f"  - Duration: {execution_duration:.2f}s (Expected <= {expected['max_execution_time_seconds']}s)")

    # Get final metrics
    metrics = orchestrator.services.metrics_collector.snapshot(session_id)
    audit_trail = orchestrator.services.audit_writer.read_trail(session_id)

    return {
        "case_name": case_name,
        "status": "PASSED",
        "discovered_leads": discovered_leads,
        "websites_analyzed": websites_analyzed,
        "successful_reports": successful_reports,
        "execution_duration_seconds": execution_duration,
        "metrics": metrics.model_dump(),
        "audit_trail_entries_count": len(audit_trail),
        "recovery_id": getattr(final_context, "recovery_id", None)
    }

async def main():
    print("==================================================")
    print("GROWTHSCOUT AI — BENCHMARK EVALUATION RUNNER")
    print("==================================================")

    # 1. Load dataset & expectations
    dataset = load_json(DATASET_PATH)
    expectations = load_json(EXPECTED_RESULTS_PATH)

    results = []
    has_failures = False

    # Run hvac_austin: standard flow + checkpoint recovery verification
    try:
        res = await run_benchmark_case(
            "hvac_austin",
            dataset["hvac_austin"],
            expectations["hvac_austin"],
            simulate_crawler_failures=False,
            test_resumption=True
        )
        results.append(res)
    except Exception as e:
        print(f"[!] Case hvac_austin FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        has_failures = True

    # Run plumbing_seattle: no-website branch validation (auditing skipped)
    try:
        res = await run_benchmark_case(
            "plumbing_seattle",
            dataset["plumbing_seattle"],
            expectations["plumbing_seattle"],
            simulate_crawler_failures=False,
            test_resumption=False
        )
        results.append(res)
    except Exception as e:
        print(f"[!] Case plumbing_seattle FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        has_failures = True

    # Run dentistry_chicago: isolated website analysis crawler failures + validation continuation
    try:
        res = await run_benchmark_case(
            "dentistry_chicago",
            dataset["dentistry_chicago"],
            expectations["dentistry_chicago"],
            simulate_crawler_failures=True,
            test_resumption=False
        )
        results.append(res)
    except Exception as e:
        print(f"[!] Case dentistry_chicago FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        has_failures = True

    # 2. Write report
    with open(RESULTS_OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[*] Benchmark execution report saved to {RESULTS_OUTPUT_PATH}")

    if has_failures:
        print("\n[!] BENCHMARK RUN ENCOUNTERED FAILURES.")
        sys.exit(1)
    else:
        print("\n[+] ALL BENCHMARK RUN CASES PASSED CONSTRAINTS.")
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
