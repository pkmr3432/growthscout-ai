# tests/orchestrator_tests/test_workflow_events.py
"""
Tests: WorkflowEvent and StdoutEventPublisher interfaces.

Validates:
  - All 7 concrete WorkflowEvent subtypes construct correctly
  - event_id pattern validation (ev_[a-f0-9]{8})
  - Subtype specific validations (duration_ms, retries_made, checkpoint_version)
  - Immutability of WorkflowEvent subtypes
  - EventPublisher protocol compatibility via runtime checks
  - StdoutEventPublisher serialization and exception handling
"""
import io
import json
import sys
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from agents.orchestrator_agent.state_machine.states import WorkflowState
from agents.orchestrator_agent.interfaces.events import (
    WorkflowEvent,
    WorkerCompleted,
    WorkerFailed,
    TransitionExecuted,
    MemoryWritten,
    CheckpointSaved,
    WorkflowPaused,
    WorkflowResumed,
    EventPublisher,
    StdoutEventPublisher,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _base_args(event_id: str = "ev_00000001") -> dict:
    return {
        "event_id": event_id,
        "session_id": "sess_12345678",
        "workflow_id": "wf_12345678",
        "occurred_at": _now(),
        "correlation_id": "corr_12345678",
    }


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestWorkflowEventBase:
    def test_valid_event_id(self):
        # Should construct without error
        evt = WorkerCompleted(
            **_base_args("ev_abcdef09"),
            worker_name="business_discovery_agent",
            output_schema="BusinessDiscoveryOutput",
            duration_ms=120.5
        )
        assert evt.event_id == "ev_abcdef09"

    def test_invalid_event_id_raises(self):
        bad_ids = [
            "bad_id",
            "ev_1234567",       # too short
            "ev_123456789",      # too long
            "EV_12345678",      # uppercase
            "ev_1234567g",      # non-hex character
        ]
        for bad_id in bad_ids:
            with pytest.raises(ValidationError) as exc_info:
                WorkerCompleted(
                    **_base_args(bad_id),
                    worker_name="business_discovery_agent",
                    output_schema="BusinessDiscoveryOutput",
                    duration_ms=120.5
                )
            assert "event_id" in str(exc_info.value)

    def test_frozen_immutability(self):
        evt = WorkerCompleted(
            **_base_args(),
            worker_name="business_discovery_agent",
            output_schema="BusinessDiscoveryOutput",
            duration_ms=120.5
        )
        with pytest.raises(Exception):
            evt.worker_name = "new_name"  # type: ignore


class TestConcreteEventTypes:
    def test_worker_completed_valid(self):
        evt = WorkerCompleted(
            **_base_args(),
            worker_name="website_analysis_agent",
            output_schema="WebsiteAnalysisOutput",
            duration_ms=500.0
        )
        assert evt.worker_name == "website_analysis_agent"
        assert evt.output_schema == "WebsiteAnalysisOutput"
        assert evt.duration_ms == 500.0

    def test_worker_completed_invalid_duration(self):
        with pytest.raises(ValidationError):
            WorkerCompleted(
                **_base_args(),
                worker_name="website_analysis_agent",
                output_schema="WebsiteAnalysisOutput",
                duration_ms=-1.0
            )

    def test_worker_failed_valid(self):
        evt = WorkerFailed(
            **_base_args(),
            worker_name="opportunity_agent",
            error_message="API Rate Limit Exceeded",
            retries_made=3
        )
        assert evt.worker_name == "opportunity_agent"
        assert evt.error_message == "API Rate Limit Exceeded"
        assert evt.retries_made == 3

    def test_worker_failed_invalid_retries(self):
        with pytest.raises(ValidationError):
            WorkerFailed(
                **_base_args(),
                worker_name="opportunity_agent",
                error_message="API Rate Limit Exceeded",
                retries_made=-1
            )

    def test_transition_executed_valid(self):
        evt = TransitionExecuted(
            **_base_args(),
            from_state=WorkflowState.IDLE,
            to_state=WorkflowState.DISCOVERING,
            reason="Kickoff workflow execution"
        )
        assert evt.from_state == WorkflowState.IDLE
        assert evt.to_state == WorkflowState.DISCOVERING
        assert evt.reason == "Kickoff workflow execution"

    def test_memory_written_valid(self):
        evt = MemoryWritten(
            **_base_args(),
            domain="discovery_results",
            keys=["google_maps_data", "social_media_profiles"],
            operation="append",
            writing_agent="business_discovery_agent"
        )
        assert evt.domain == "discovery_results"
        assert evt.keys == ["google_maps_data", "social_media_profiles"]
        assert evt.operation == "append"
        assert evt.writing_agent == "business_discovery_agent"

    def test_checkpoint_saved_valid(self):
        evt = CheckpointSaved(
            **_base_args(),
            checkpoint_version=5,
            context_state=WorkflowState.OPPORTUNITY_ANALYSIS
        )
        assert evt.checkpoint_version == 5
        assert evt.context_state == WorkflowState.OPPORTUNITY_ANALYSIS

    def test_checkpoint_saved_invalid_version(self):
        with pytest.raises(ValidationError):
            CheckpointSaved(
                **_base_args(),
                checkpoint_version=0,
                context_state=WorkflowState.OPPORTUNITY_ANALYSIS
            )

    def test_workflow_paused_valid(self):
        evt = WorkflowPaused(
            **_base_args(),
            pause_reason="awaiting_approval",
            paused_at_state=WorkflowState.LEAD_PARTITIONING
        )
        assert evt.pause_reason == "awaiting_approval"
        assert evt.paused_at_state == WorkflowState.LEAD_PARTITIONING

    def test_workflow_resumed_valid(self):
        evt = WorkflowResumed(
            **_base_args(),
            resumed_from_state=WorkflowState.LEAD_PARTITIONING,
            checkpoint_version=3
        )
        assert evt.resumed_from_state == WorkflowState.LEAD_PARTITIONING
        assert evt.checkpoint_version == 3

    def test_workflow_resumed_invalid_version(self):
        with pytest.raises(ValidationError):
            WorkflowResumed(
                **_base_args(),
                resumed_from_state=WorkflowState.LEAD_PARTITIONING,
                checkpoint_version=0
            )


class TestStdoutEventPublisher:
    def test_protocol_compatibility(self):
        publisher = StdoutEventPublisher()
        assert isinstance(publisher, EventPublisher)

    def test_publish_output(self):
        publisher = StdoutEventPublisher()
        evt = WorkerCompleted(
            **_base_args("ev_12345678"),
            worker_name="business_discovery_agent",
            output_schema="BusinessDiscoveryOutput",
            duration_ms=120.5
        )

        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            publisher.publish(evt)
        finally:
            sys.stdout = sys.__stdout__

        printed_str = captured_output.getvalue().strip()
        assert printed_str != ""
        
        # Verify it is valid JSON and contains appropriate fields
        data = json.loads(printed_str)
        assert data["event_type"] == "WorkerCompleted"
        assert data["event_id"] == "ev_12345678"
        assert data["worker_name"] == "business_discovery_agent"
        assert data["duration_ms"] == 120.5

    def test_publish_never_raises(self):
        publisher = StdoutEventPublisher()
        
        # Mock class to cause serialization failure
        class BadEvent(WorkflowEvent):
            bad_field: object

        # Create a dummy bad event without passing the validators,
        # or construct a mock event that raises on dump_json
        class FailEvent:
            def model_dump_json(self):
                raise RuntimeError("Serialization failed")

        bad_event = FailEvent()
        
        captured_output = io.StringIO()
        sys.stdout = captured_output
        try:
            # Should not raise any exceptions
            publisher.publish(bad_event)  # type: ignore
        finally:
            sys.stdout = sys.__stdout__

        # Assert no output was printed (or it handled it silently)
        assert captured_output.getvalue().strip() == ""
