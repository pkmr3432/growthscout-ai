# tests/integration_tests/test_live_mcp_integration.py
import os
import uuid
from datetime import datetime, timezone
import pytest

from agents.orchestrator_agent.runtime_config import RuntimeConfig
from agents.orchestrator_agent.agent import GrowthScoutOrchestrator
from agents.orchestrator_agent.state_machine.workflow_context import (
    WorkflowContext,
    WorkflowMetadata,
    ExecutionMetadata,
    WorkflowTimestamps,
)
from agents.orchestrator_agent.state_machine.states import WorkflowState

@pytest.mark.live
@pytest.mark.asyncio
async def test_live_mcp_integration_flow():
    # Only run if live keys are present in the environment
    maps_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    if not maps_key or not gemini_key:
        pytest.skip("Skipping live integration test: GOOGLE_MAPS_API_KEY or GEMINI_API_KEY not configured.")

    config = RuntimeConfig.load_from_env()
    
    # Deterministic startup sequence
    orchestrator = await GrowthScoutOrchestrator.initialize(config=config, bypass_preflight=False)

    # Construct context
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
    correlation_id = f"corr_{uuid.uuid4().hex[:8]}"
    
    now = datetime.now(timezone.utc)
    context = WorkflowContext(
        session_id=session_id,
        workflow_id=workflow_id,
        current_state=WorkflowState.IDLE,
        execution_metadata=ExecutionMetadata(
            orchestrator_version="4.0",
            adk_version="1.0.0",
            correlation_id=correlation_id
        ),
        workflow_metadata=WorkflowMetadata(
            niche="Dentist",
            location="Austin, TX",
            max_leads=1
        ),
        timestamps=WorkflowTimestamps(
            created_at=now,
            updated_at=now,
            state_entered_at=now
        )
    )

    # Run the workflow
    res_context = await orchestrator.start_workflow(context)
    
    # Assert we successfully progressed
    assert res_context.current_state in (
        WorkflowState.AWAITING_APPROVAL,
        WorkflowState.REPORT_GENERATION,
        WorkflowState.OPPORTUNITY_ANALYSIS,
        WorkflowState.COMPLETED,
    )
