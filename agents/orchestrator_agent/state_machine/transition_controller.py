# agents/orchestrator_agent/state_machine/transition_controller.py
"""
Pure-validation transition controller for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole authority for committing transitions)

TransitionController is a stateless, side-effect-free validator.
It NEVER:
  - mutates WorkflowContext
  - writes memory
  - writes checkpoints
  - invokes workers
  - publishes events

It only evaluates whether a proposed transition is legal and returns a
strongly typed TransitionResult. The orchestrator (agent.py) decides
whether to commit the transition based on the result.

Invariants:
  - acting_agent must equal "orchestrator_agent" for any transition to be APPROVED.
  - Transitions to states not in StateNode.allowed_transitions are DENIED.
  - Transitions from terminal states are always DENIED.
  - The returned TransitionResult.audit_entry is a pre-built AuditTrailEntry
    ready for the orchestrator to hand to AuditTrailWriter.append().
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .states import WorkflowState, WORKFLOW_TOPOLOGY, TERMINAL_STATES
from .workflow_context import WorkflowContext
from ..hooks.audit_trail import AuditTrailEntry, AuditEventType

_ORCHESTRATOR_AGENT_NAME = "orchestrator_agent"


def _new_entry_id() -> str:
    """Generate a valid evt_[hex8] entry ID."""
    return f"evt_{uuid.uuid4().hex[:8]}"


# ─── TransitionValidationStatus ───────────────────────────────────────────────

class TransitionValidationStatus(str, Enum):
    """
    Outcome of a transition validation attempt.

    APPROVED                   — transition is legal and may be committed
    DENIED_UNAUTHORIZED_AGENT  — acting_agent is not orchestrator_agent
    DENIED_WORKER_TO_WORKER    — target state agent != expected (never used directly
                                  since workers can't call validate(), but kept as a
                                  defensive category)
    DENIED_INVALID_TRANSITION  — target state not in current StateNode.allowed_transitions
    DENIED_TERMINAL_STATE      — current state is terminal; no further transitions permitted
    """
    APPROVED = "APPROVED"
    DENIED_UNAUTHORIZED_AGENT = "DENIED_UNAUTHORIZED_AGENT"
    DENIED_WORKER_TO_WORKER = "DENIED_WORKER_TO_WORKER"
    DENIED_INVALID_TRANSITION = "DENIED_INVALID_TRANSITION"
    DENIED_TERMINAL_STATE = "DENIED_TERMINAL_STATE"


# ─── MemoryAction ─────────────────────────────────────────────────────────────

class MemoryAction(BaseModel):
    """
    Describes a memory operation the orchestrator should perform after committing
    the transition. These are advisory — the orchestrator validates each action
    with MemoryGovernor before executing it.

    Inputs:
      operation: "write" or "read"
      domain:    Canonical memory domain name (from memory_bank_config.yaml)
      keys:      List of keys within the domain
      policy:    Write policy to apply
    """
    model_config = {"frozen": True}

    operation: Literal["write", "read"] = Field(
        ..., description="Memory operation type."
    )
    domain: str = Field(..., description="Target canonical memory domain.")
    keys: List[str] = Field(..., description="Keys within the domain.")
    policy: Literal["overwrite", "append", "append_only_immutable"] = Field(
        default="overwrite",
        description="Write policy governing this operation.",
    )


# ─── TransitionResult ─────────────────────────────────────────────────────────

class TransitionResult(BaseModel):
    """
    Strongly typed output of TransitionController.validate().

    The orchestrator examines is_valid before committing any state change.
    The pre-built audit_entry should be passed directly to
    AuditTrailWriter.append() after the transition is committed.

    Inputs:  (returned by TransitionController.validate())
    Outputs:
      is_valid:                True when validation_status == APPROVED
      previous_state:          The state being exited
      next_state:              The state to enter (if approved)
      transition_reason:       Human-readable description of the transition
      transition_timestamp:    UTC time the validation was computed
      audit_entry:             Pre-built AuditTrailEntry (always present)
      required_memory_actions: Advisory list of memory operations for the orchestrator
      validation_status:       Detailed outcome category
      denial_reason:           Human-readable denial message (None when APPROVED)
    """
    model_config = {"frozen": True}

    is_valid: bool = Field(..., description="True when the transition may be committed.")
    previous_state: WorkflowState = Field(..., description="State being exited.")
    next_state: WorkflowState = Field(..., description="State to enter (if approved).")
    transition_reason: str = Field(..., description="Human-readable reason for this transition.")
    transition_timestamp: datetime = Field(..., description="UTC time validation was computed.")
    audit_entry: AuditTrailEntry = Field(
        ...,
        description="Pre-built audit record ready for AuditTrailWriter.append().",
    )
    required_memory_actions: List[MemoryAction] = Field(
        default_factory=list,
        description="Advisory memory operations the orchestrator should perform.",
    )
    validation_status: TransitionValidationStatus = Field(
        ...,
        description="Detailed outcome category.",
    )
    denial_reason: Optional[str] = Field(
        None,
        description="Human-readable explanation for denied transitions.",
    )


# ─── TransitionController ─────────────────────────────────────────────────────

class TransitionController:
    """
    Pure-validation transition controller.

    Ownership: injected into orchestrator agent.py as a dependency.
    Inputs:    WorkflowContext, requested next state, acting agent name, reason
    Outputs:   TransitionResult (never mutates any external state)

    Invariants:
      - Stateless: no instance variables; every call is independent.
      - No side effects: does not write memory, audit trail, checkpoints, or events.
      - acting_agent must equal "orchestrator_agent" for APPROVED status.
    """

    def validate(
        self,
        context: WorkflowContext,
        requested_next: WorkflowState,
        acting_agent: str,
        reason: str,
    ) -> TransitionResult:
        """
        Validate a proposed state transition.

        Args:
          context:        Current WorkflowContext (read-only).
          requested_next: The WorkflowState the orchestrator wants to enter.
          acting_agent:   Name of the agent requesting the transition.
          reason:         Human-readable justification.

        Returns:
          TransitionResult with is_valid=True if the transition may be committed,
          or is_valid=False with a denial_reason explaining why.
        """
        now = datetime.now(timezone.utc)
        current_state = context.current_state
        current_node = WORKFLOW_TOPOLOGY[current_state]

        # ── Validate authority ────────────────────────────────────────────────
        if acting_agent != _ORCHESTRATOR_AGENT_NAME:
            return self._deny(
                context=context,
                requested_next=requested_next,
                reason=reason,
                status=TransitionValidationStatus.DENIED_UNAUTHORIZED_AGENT,
                denial_reason=(
                    f"Transition authority violation: '{acting_agent}' is not authorised "
                    f"to execute transitions. Only '{_ORCHESTRATOR_AGENT_NAME}' may do so."
                ),
                timestamp=now,
            )

        # ── Validate terminal state ───────────────────────────────────────────
        if current_state in TERMINAL_STATES:
            return self._deny(
                context=context,
                requested_next=requested_next,
                reason=reason,
                status=TransitionValidationStatus.DENIED_TERMINAL_STATE,
                denial_reason=(
                    f"Cannot transition from terminal state '{current_state.value}'. "
                    "Terminal states have no allowed transitions."
                ),
                timestamp=now,
            )

        # ── Validate transition is allowed ───────────────────────────────────
        if requested_next not in current_node.allowed_transitions and requested_next != WorkflowState.FAILED:
            return self._deny(
                context=context,
                requested_next=requested_next,
                reason=reason,
                status=TransitionValidationStatus.DENIED_INVALID_TRANSITION,
                denial_reason=(
                    f"Transition from '{current_state.value}' to '{requested_next.value}' "
                    f"is not permitted. Allowed transitions: "
                    f"{[s.value for s in current_node.allowed_transitions]}"
                ),
                timestamp=now,
            )

        # ── Build required memory actions from the destination node ───────────
        next_node = WORKFLOW_TOPOLOGY[requested_next]
        memory_actions = [
            MemoryAction(operation="write", domain=domain, keys=[], policy="overwrite")
            for domain in next_node.memory_write_domains
        ] + [
            MemoryAction(operation="read", domain=domain, keys=[], policy="overwrite")
            for domain in next_node.memory_read_domains
        ]

        # ── Build pre-computed audit entry ────────────────────────────────────
        audit_entry = AuditTrailEntry(
            entry_id=_new_entry_id(),
            session_id=context.session_id,
            workflow_id=context.workflow_id,
            event_type=AuditEventType.STATE_ENTERED,
            workflow_state=requested_next,
            acting_agent=acting_agent,
            timestamp=now,
            input_references=[current_state.value],
            output_references=[requested_next.value],
            transition_reason=reason,
            partition_summary=context.partition_summary,
        )

        return TransitionResult(
            is_valid=True,
            previous_state=current_state,
            next_state=requested_next,
            transition_reason=reason,
            transition_timestamp=now,
            audit_entry=audit_entry,
            required_memory_actions=memory_actions,
            validation_status=TransitionValidationStatus.APPROVED,
            denial_reason=None,
        )

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _deny(
        self,
        context: WorkflowContext,
        requested_next: WorkflowState,
        reason: str,
        status: TransitionValidationStatus,
        denial_reason: str,
        timestamp: datetime,
    ) -> TransitionResult:
        """Build a denial TransitionResult with a VALIDATION_FAILED audit entry."""
        audit_entry = AuditTrailEntry(
            entry_id=_new_entry_id(),
            session_id=context.session_id,
            workflow_id=context.workflow_id,
            event_type=AuditEventType.VALIDATION_FAILED,
            workflow_state=context.current_state,
            acting_agent="orchestrator_agent",
            timestamp=timestamp,
            input_references=[context.current_state.value],
            output_references=[requested_next.value],
            transition_reason=denial_reason,
            partition_summary=context.partition_summary,
            metadata={"denial_status": status.value},
        )
        return TransitionResult(
            is_valid=False,
            previous_state=context.current_state,
            next_state=requested_next,
            transition_reason=reason,
            transition_timestamp=timestamp,
            audit_entry=audit_entry,
            required_memory_actions=[],
            validation_status=status,
            denial_reason=denial_reason,
        )
