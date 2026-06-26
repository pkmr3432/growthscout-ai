# agents/orchestrator_agent/hooks/audit_trail.py
"""
Immutable, append-only audit trail for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole writer)

This module implements:
  - AuditEventType enum — 10 event categories covering state, worker,
    memory, checkpoint, and validation lifecycle events
  - AuditTrailEntry — typed, frozen model for each audit record
  - AuditTrailWriter — append-only writer enforcing immutability per session

Invariants:
  - Entries are append-only: duplicate entry_id within a session raises
    ImmutabilityViolationError.
  - AuditTrailWriter is a pure data store — it never mutates WorkflowContext,
    publishes events, or invokes workers.
  - entry_id must match pattern: evt_[a-f0-9]{8}
  - Required fields per workflow_specification.md §10:
      session_id, workflow_state, acting_agent, timestamp,
      input_references, output_references, transition_reason, partition_summary
  - Phase 4A backing store: in-memory dict keyed by session_id.
    Phase 5 target: Firestore with write_policy=append_only_immutable.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from ..state_machine.states import WorkflowState
from ..state_machine.workflow_context import PartitionSummary
from ..exceptions import ImmutabilityViolationError

_ENTRY_ID_PATTERN = re.compile(r"^evt_[a-f0-9]{8}$")


# ─── AuditEventType ───────────────────────────────────────────────────────────

class AuditEventType(str, Enum):
    """
    10-category taxonomy of auditable workflow events.

    STATE_*       — state machine transitions
    WORKER_*      — worker agent lifecycle
    MEMORY_*      — governed memory operations
    CHECKPOINT_*  — workflow persistence
    VALIDATION_*  — evidence or governance failures
    """
    STATE_ENTERED = "STATE_ENTERED"
    STATE_EXITED = "STATE_EXITED"
    WORKER_STARTED = "WORKER_STARTED"
    WORKER_COMPLETED = "WORKER_COMPLETED"
    WORKER_FAILED = "WORKER_FAILED"
    MEMORY_WRITE = "MEMORY_WRITE"
    MEMORY_READ = "MEMORY_READ"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    SCHEMA_VALIDATION_FAILED = "SCHEMA_VALIDATION_FAILED"
    BUSINESS_VALIDATION_FAILED = "BUSINESS_VALIDATION_FAILED"
    OUTPUT_NORMALIZED = "OUTPUT_NORMALIZED"
    VALIDATION_SUCCEEDED = "VALIDATION_SUCCEEDED"
    RETRY_STARTED = "RETRY_STARTED"
    RETRY_COMPLETED = "RETRY_COMPLETED"
    CIRCUIT_OPENED = "CIRCUIT_OPENED"
    CIRCUIT_HALF_OPEN = "CIRCUIT_HALF_OPEN"
    CIRCUIT_CLOSED = "CIRCUIT_CLOSED"
    TIMEOUT_OCCURRED = "TIMEOUT_OCCURRED"
    WORKFLOW_RECOVERY_FAILED = "WORKFLOW_RECOVERY_FAILED"


# ─── AuditTrailEntry ──────────────────────────────────────────────────────────

class AuditTrailEntry(BaseModel):
    """
    Immutable audit record for a single workflow event.

    Inputs (all required unless Optional):
      entry_id:          Unique entry identifier (pattern: evt_[hex8])
      session_id:        Session this entry belongs to
      workflow_id:       Workflow run this entry belongs to
      event_type:        Category from AuditEventType
      workflow_state:    Active WorkflowState when the event occurred
      acting_agent:      Agent name performing the action
      timestamp:         UTC time of the event
      input_references:  Keys/IDs of inputs consumed
      output_references: Keys/IDs of outputs produced
      transition_reason: Human-readable description of why this event occurred
      partition_summary: Populated for LEAD_PARTITIONING events (else None)
      metadata:          Event-specific additional key-value pairs

    Invariant: Once created, this record is immutable (model_config frozen=True).
    """
    model_config = {"frozen": True}

    entry_id: str = Field(
        ...,
        description="Unique entry ID. Pattern: evt_[a-f0-9]{8}",
    )
    session_id: str = Field(..., description="Session scope for this entry.")
    workflow_id: str = Field(..., description="Workflow run scope for this entry.")
    event_type: AuditEventType = Field(..., description="Category of the audited event.")
    workflow_state: WorkflowState = Field(..., description="Active state when event occurred.")
    acting_agent: str = Field(..., description="Agent performing the action.")
    timestamp: datetime = Field(..., description="UTC timestamp of the event.")
    input_references: List[str] = Field(
        default_factory=list,
        description="Keys or IDs of data consumed by this operation.",
    )
    output_references: List[str] = Field(
        default_factory=list,
        description="Keys or IDs of data produced by this operation.",
    )
    transition_reason: str = Field(
        ...,
        description="Human-readable reason for this event (required by workflow_specification.md §10).",
    )
    partition_summary: Optional[PartitionSummary] = Field(
        None,
        description="Lead partition counts; non-null for LEAD_PARTITIONING events.",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict,
        description="Event-specific additional key-value pairs.",
    )
    recovery_id: Optional[str] = Field(
        None,
        description="Optional recovery ID associated with a resumed run.",
    )

    @field_validator("entry_id")
    @classmethod
    def _validate_entry_id(cls, v: str) -> str:
        if not _ENTRY_ID_PATTERN.match(v):
            raise ValueError(
                f"entry_id '{v}' does not match required pattern evt_[a-f0-9]{{8}}"
            )
        return v


# ─── AuditTrailWriter ─────────────────────────────────────────────────────────

class AuditTrailWriter:
    """
    Append-only audit trail writer for the GrowthScout AI Orchestrator.

    Ownership: orchestrator_agent — the only component authorised to write.
    Inputs:  AuditTrailEntry instances
    Outputs: Read-only views of stored entries

    Invariants:
      - append() raises ImmutabilityViolationError if entry_id already exists
        for the given session_id. This enforces the write_policy=append_only_immutable
        contract from workflow_routing.yaml.
      - AuditTrailWriter never modifies WorkflowContext, publishes events,
        invokes workers, or writes checkpoints.
      - Phase 4A: in-memory store (dict[session_id] → list[AuditTrailEntry]).
        Swap the backing store in Phase 5 without changing the public API.
    """

    def __init__(self) -> None:
        # session_id → ordered list of entries (insertion order preserved)
        self._store: Dict[str, List[AuditTrailEntry]] = defaultdict(list)
        # session_id → set of known entry_ids (for O(1) duplicate detection)
        self._ids: Dict[str, set[str]] = defaultdict(set)

    def append(self, entry: AuditTrailEntry) -> None:
        """
        Append an audit entry to the trail for its session.

        Raises:
          ImmutabilityViolationError: If entry_id already exists in this session's trail.
        """
        session_id = entry.session_id
        if entry.entry_id in self._ids[session_id]:
            raise ImmutabilityViolationError(
                f"Immutability violation: entry_id '{entry.entry_id}' already exists "
                f"in audit trail for session '{session_id}'. "
                "Audit trail entries cannot be modified or re-appended."
            )
        self._store[session_id].append(entry)
        self._ids[session_id].add(entry.entry_id)

    def read_trail(self, session_id: str) -> List[AuditTrailEntry]:
        """
        Return all audit entries for a session in insertion order.

        Returns an empty list if no entries exist (not an error condition).
        """
        return list(self._store[session_id])

    def find_by_event_type(
        self,
        session_id: str,
        event_type: AuditEventType,
    ) -> List[AuditTrailEntry]:
        """
        Return all entries for a session matching the specified event type.
        """
        return [
            entry
            for entry in self._store[session_id]
            if entry.event_type == event_type
        ]

    def count(self, session_id: str) -> int:
        """Return the total number of entries for a session."""
        return len(self._store[session_id])

    def session_ids(self) -> List[str]:
        """Return the list of all session IDs with at least one entry."""
        return [sid for sid, entries in self._store.items() if entries]
