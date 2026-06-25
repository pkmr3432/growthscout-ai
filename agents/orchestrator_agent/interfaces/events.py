# agents/orchestrator_agent/interfaces/events.py
"""
Workflow event interface definitions for GrowthScout AI.

Ownership: orchestrator_agent (publishes events after successful operations)

This module defines:
  - WorkflowEvent — abstract base model for all events
  - EventPublisher — protocol interface for event sinks
  - 7 concrete event types covering worker, transition, memory, checkpoint,
    and workflow lifecycle operations
  - StdoutEventPublisher — Phase 4A default implementation (structured JSON)

Invariants:
  - Events are published ONLY after successful operations, never before.
  - No event bus, Pub/Sub, or OpenTelemetry wiring is included here (Phase 5).
  - All event models are frozen (immutable after construction).
  - event_id must match pattern: ev_[a-f0-9]{8}

Design note:
  The orchestrator calls EventPublisher.publish(); consumers (telemetry,
  monitoring) attach at a higher layer in future phases. This decouples
  logging and observability from core orchestration logic.
"""
from __future__ import annotations

import json
import re
from abc import abstractmethod
from datetime import datetime
from typing import List, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator

from ..state_machine.states import WorkflowState

_EVENT_ID_PATTERN = re.compile(r"^ev_[a-f0-9]{8}$")


# ─── Base Event ───────────────────────────────────────────────────────────────

class WorkflowEvent(BaseModel):
    """
    Abstract base for all GrowthScout AI workflow events.

    Inputs:
      event_id:       Unique event identifier (pattern: ev_[hex8])
      session_id:     Session this event belongs to
      workflow_id:    Workflow run this event belongs to
      occurred_at:    UTC timestamp of the event
      correlation_id: Ties this event to the originating request/worker call

    Invariant: event_id must match ev_[a-f0-9]{8}
    """
    model_config = {"frozen": True}

    event_id: str = Field(..., description="Unique event ID. Pattern: ev_[a-f0-9]{8}")
    session_id: str = Field(..., description="Session this event is scoped to.")
    workflow_id: str = Field(..., description="Workflow run this event is scoped to.")
    occurred_at: datetime = Field(..., description="UTC timestamp when the event occurred.")
    correlation_id: str = Field(..., description="Links this event to a worker invocation or request.")

    @field_validator("event_id")
    @classmethod
    def _validate_event_id(cls, v: str) -> str:
        if not _EVENT_ID_PATTERN.match(v):
            raise ValueError(
                f"event_id '{v}' does not match required pattern ev_[a-f0-9]{{8}}"
            )
        return v


# ─── Concrete Event Types ─────────────────────────────────────────────────────

class WorkerCompleted(WorkflowEvent):
    """
    Published after a worker agent successfully returns its output.

    Invariant: Published ONLY after the worker's output has been validated
               and accepted — never speculatively.
    """
    worker_name: str = Field(..., description="Name of the worker agent that completed.")
    output_schema: str = Field(..., description="Name of the Pydantic output class returned.")
    duration_ms: float = Field(..., ge=0.0, description="Total invocation duration in milliseconds.")


class WorkerFailed(WorkflowEvent):
    """
    Published after a worker invocation fails following all retries.

    Invariant: retries_made reflects total attempts, not additional retries.
    """
    worker_name: str = Field(..., description="Name of the worker agent that failed.")
    error_message: str = Field(..., description="Human-readable failure description.")
    retries_made: int = Field(..., ge=0, description="Number of invocation attempts made.")


class TransitionExecuted(WorkflowEvent):
    """
    Published after the orchestrator successfully commits a state transition.

    Invariant: Published ONLY after context.current_state has been updated
               and the audit entry has been written — never before commitment.
    """
    from_state: WorkflowState = Field(..., description="State exited.")
    to_state: WorkflowState = Field(..., description="State entered.")
    reason: str = Field(..., description="Human-readable reason for the transition.")


class MemoryWritten(WorkflowEvent):
    """
    Published after the orchestrator successfully writes to a memory domain.
    """
    domain: str = Field(..., description="Canonical memory domain written to.")
    keys: List[str] = Field(..., description="Keys written within the domain.")
    operation: str = Field(..., description="Write policy applied: overwrite / append / append_only_immutable.")
    writing_agent: str = Field(..., description="Agent authorised to perform this write.")


class CheckpointSaved(WorkflowEvent):
    """
    Published after CheckpointInterface.save() completes successfully.
    """
    checkpoint_version: int = Field(..., ge=1, description="Monotonic checkpoint version number.")
    context_state: WorkflowState = Field(..., description="WorkflowState captured in the checkpoint.")


class WorkflowPaused(WorkflowEvent):
    """
    Published when the orchestrator suspends workflow execution.

    pause_reason values:
      - "awaiting_approval"  — HITL gate (Phase 4B)
      - "timeout"            — worker agent timed out
      - "rate_limit"         — API quota reached
    """
    pause_reason: str = Field(..., description="Reason for the pause.")
    paused_at_state: WorkflowState = Field(..., description="State where execution was suspended.")


class WorkflowResumed(WorkflowEvent):
    """
    Published when ResumabilityController successfully restores a halted workflow.
    """
    resumed_from_state: WorkflowState = Field(..., description="State restored from checkpoint.")
    checkpoint_version: int = Field(..., ge=1, description="Checkpoint version used for restoration.")


# ─── EventPublisher Protocol ──────────────────────────────────────────────────

@runtime_checkable
class EventPublisher(Protocol):
    """
    Protocol interface for event sinks.

    Ownership: orchestrator_agent calls publish(); consumers attach externally.
    Inputs:  event — any WorkflowEvent subtype
    Outputs: None (fire-and-forget; errors are logged, not raised)

    Phase 4A default: StdoutEventPublisher
    Phase 5 target:   Cloud Pub/Sub / OpenTelemetry span
    """

    @abstractmethod
    def publish(self, event: WorkflowEvent) -> None:
        """Publish a workflow event to the configured sink."""
        ...


# ─── Default Implementation ───────────────────────────────────────────────────

class StdoutEventPublisher:
    """
    Phase 4A default EventPublisher — writes structured JSON to stdout.

    Purpose:  Provides a concrete publisher for unit tests and local runs
              without requiring any external infrastructure.
    Ownership: Injected by orchestrator agent.py; can be replaced in tests.
    Invariant: publish() never raises; errors are silently swallowed to
               prevent observability from breaking the workflow.
    """

    def publish(self, event: WorkflowEvent) -> None:
        """Serialize event to structured JSON and write to stdout."""
        try:
            payload = {
                "event_type": type(event).__name__,
                **json.loads(event.model_dump_json()),
            }
            print(json.dumps(payload))
        except Exception:
            # Observability must NEVER break workflow execution.
            pass
