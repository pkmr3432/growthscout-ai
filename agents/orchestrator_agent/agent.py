# agents/orchestrator_agent/agent.py
"""
Orchestrator Agent — GrowthScout AI coordination hub.

Ownership: This module is the sole site where WorkflowContext is mutated.
           All other Phase 4A components are pure; only this module commits
           state transitions, memory decisions, audit entries, and events.

This module:
  1. Instantiates the orchestrator LlmAgent via google-adk.
  2. Defines OrchestratorDependencies — the DI container for all Phase 4A components.
  3. Defines GrowthScoutOrchestrator — the coordination class that wires
     all foundation components together and provides the orchestrate() method.

Phase 4A scope (per approved plan):
  - Orchestrator foundation and coordination scaffolding only.
  - No full workflow DAG wiring (Phase 4B).
  - No HITL loop (Phase 4B).
  - No Firestore persistence (Phase 5).
  - No Pub/Sub / OpenTelemetry (Phase 5).
  - No distributed execution (Phase 5).

Invariants:
  - agent.tools == [] — orchestrator has no direct MCP access.
  - Only GrowthScoutOrchestrator.orchestrate() may:
      * call TransitionController.validate() and commit transitions
      * call MemoryGovernor.evaluate_*() and act on the decision
      * call AuditTrailWriter.append()
      * call CheckpointInterface.save()
      * call EventPublisher.publish()
      * create new WorkflowContext instances
  - Worker-to-worker invocation remains impossible:
      WorkerRegistry exposes only single-name lookups;
      workers never receive WorkerRegistry as a dependency.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import yaml
from google.adk.agents import LlmAgent

from .state_machine.states import WORKFLOW_TOPOLOGY, WorkflowState
from .state_machine.workflow_context import WorkflowContext
from .state_machine.transition_controller import TransitionController
from .state_machine.memory_governor import MemoryGovernor
from .hooks.audit_trail import AuditTrailWriter, AuditEventType, AuditTrailEntry
from .hooks.evidence_validator import EvidenceValidationHook
from .interfaces.worker_invocation import WorkerRegistry
from .interfaces.checkpoint import CheckpointInterface
from .interfaces.resumability import ResumabilityController
from .interfaces.events import (
    EventPublisher,
    StdoutEventPublisher,
    TransitionExecuted,
    CheckpointSaved,
    WorkflowPaused,
    WorkflowResumed,
    MemoryWritten,
)
from .exceptions import InvalidTransitionError, EvidenceValidationError

from .failure_policy import FailurePolicy
from .metrics_collector import WorkflowMetricsCollector, InMemoryMetricsCollector
from .workflow_executor import WorkflowExecutor, TransitionPlan, TraceEntry, ExecutionTrace

# ─── Paths ────────────────────────────────────────────────────────────────────

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.abspath(os.path.join(_AGENT_DIR, "..", ".."))
_POLICY_DIR = os.path.join(_ROOT_DIR, "agents", "shared", "policies")
_CONFIG_PATH = os.path.join(_AGENT_DIR, "definition.yaml")


def _load_config() -> dict:
    """Load the orchestrator definition.yaml."""
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)["agent"]


def _load_policies() -> str:
    """Load and concatenate all shared policies."""
    policies = []
    for policy_file in ["safety_policy.md", "evidence_policy.md", "grounding_policy.md"]:
        p_path = os.path.join(_POLICY_DIR, policy_file)
        if os.path.exists(p_path):
            with open(p_path, "r") as pf:
                policies.append(pf.read())
    return "\n\n".join(policies)


# ─── Dependency Container ─────────────────────────────────────────────────────

@dataclass
class OrchestratorDependencies:
    """
    Dependency injection container for all orchestrator components.
    """
    transition_controller: TransitionController = field(
        default_factory=TransitionController
    )
    memory_governor: MemoryGovernor = field(
        default_factory=MemoryGovernor
    )
    worker_registry: WorkerRegistry = field(
        default_factory=WorkerRegistry
    )
    evidence_validator: EvidenceValidationHook = field(
        default_factory=EvidenceValidationHook
    )
    audit_writer: AuditTrailWriter = field(
        default_factory=AuditTrailWriter
    )
    checkpoint_interface: CheckpointInterface = field(
        default_factory=CheckpointInterface
    )
    event_publisher: EventPublisher = field(
        default_factory=StdoutEventPublisher  # type: ignore[arg-type]
    )
    failure_policy: FailurePolicy = field(
        default_factory=FailurePolicy
    )
    metrics_collector: WorkflowMetricsCollector = field(
        default_factory=InMemoryMetricsCollector
    )

    def __post_init__(self) -> None:
        # ResumabilityController depends on CheckpointInterface — wire after init
        self.resumability_controller = ResumabilityController(
            checkpoint_interface=self.checkpoint_interface
        )


# ─── GrowthScoutOrchestrator ──────────────────────────────────────────────────

class GrowthScoutOrchestrator:
    """
    Core coordination class for GrowthScout AI.
    """

    def __init__(self, deps: OrchestratorDependencies) -> None:
        self.deps = deps
        self._tc = deps.transition_controller
        self._mg = deps.memory_governor
        self._wr = deps.worker_registry
        self._ev = deps.evidence_validator
        self._aw = deps.audit_writer
        self._ci = deps.checkpoint_interface
        self._ep = deps.event_publisher
        self._rc = deps.resumability_controller
        self._fp = deps.failure_policy
        self._mc = deps.metrics_collector
        self._executor = WorkflowExecutor(
            tc=self._tc,
            wr=self._wr,
            mg=self._mg,
            ev=self._ev,
            aw=self._aw,
            ci=self._ci,
            ep=self._ep,
            rc=self._rc,
            fp=self._fp,
            mc=self._mc,
        )

    # ─── Core coordination ────────────────────────────────────────────────────

    async def start_workflow(self, context: WorkflowContext) -> WorkflowContext:
        """Start execution loop from context's current state."""
        return await self._executor.execute_to_gate(context)

    async def submit_hitl_action(
        self,
        session_id: str,
        approved: bool,
        feedback: Optional[str] = None,
    ) -> WorkflowContext:
        """Submit HITL review approval/rejection callback."""
        checkpoint = self._ci.load(session_id)
        context = checkpoint.context_snapshot

        if context.current_state != WorkflowState.AWAITING_APPROVAL:
            raise InvalidTransitionError(
                f"Cannot submit HITL action in state {context.current_state.value}. "
                "Must be in AWAITING_APPROVAL."
            )

        now = datetime.now(timezone.utc)
        if approved:
            # Transition AWAITING_APPROVAL -> COMPLETED
            plan = TransitionPlan(
                target_state=WorkflowState.COMPLETED,
                context_patch={},
                create_checkpoint=True,
                publish_events=True,
            )
            context = self._executor._apply_transition_plan(context, plan, "orchestrator_agent", "User approved growth report.")
            self._executor._add_trace_entry(session_id, context.workflow_id, "terminal_status", {"state": WorkflowState.COMPLETED.value})
            self._mc.record_completion(session_id, success=True)
            return context
        else:
            # Rejection flow
            if context.revision_count >= 5:
                plan = TransitionPlan(
                    target_state=WorkflowState.FAILED,
                    context_patch={},
                    create_checkpoint=True,
                    publish_events=True,
                    metadata={"reason": "maximum_revision_cycles_exceeded"}
                )
                context = self._executor._apply_transition_plan(context, plan, "orchestrator_agent", "HITL Revisions limit exceeded.")
                self._executor._add_trace_entry(session_id, context.workflow_id, "terminal_status", {"state": WorkflowState.FAILED.value})
                self._mc.record_completion(session_id, success=False)
                return context
            else:
                if feedback:
                    self._ep.publish(MemoryWritten(
                        event_id=f"ev_{uuid.uuid4().hex[:8]}",
                        session_id=session_id,
                        workflow_id=context.workflow_id,
                        occurred_at=now,
                        correlation_id=context.execution_metadata.correlation_id,
                        domain="human_notes",
                        keys=["reviewer_feedback"],
                        operation="append",
                        writing_agent="orchestrator_agent"
                    ))
                    ev_entry = AuditTrailEntry(
                        entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                        session_id=session_id,
                        workflow_id=context.workflow_id,
                        event_type=AuditEventType.VALIDATION_FAILED,
                        workflow_state=context.current_state,
                        acting_agent="orchestrator_agent",
                        timestamp=now,
                        input_references=[],
                        output_references=[],
                        transition_reason=feedback,
                        partition_summary=context.partition_summary,
                    )
                    self._aw.append(ev_entry)

                new_revision_count = context.revision_count + 1
                plan = TransitionPlan(
                    target_state=WorkflowState.REPORT_GENERATION,
                    context_patch={"revision_count": new_revision_count},
                    create_checkpoint=True,
                    publish_events=True,
                )
                context = self._executor._apply_transition_plan(context, plan, "orchestrator_agent", f"User rejected report. Feedback: {feedback or 'No feedback'}")
                return await self._executor.execute_to_gate(context)

    def request_transition(
        self,
        context: WorkflowContext,
        requested_next: WorkflowState,
        reason: str,
    ) -> WorkflowContext:
        """Fallback for Phase 4A compatibility."""
        plan = TransitionPlan(
            target_state=requested_next,
            create_checkpoint=True,
            publish_events=True
        )
        return self._executor._apply_transition_plan(context, plan, "orchestrator_agent", reason)

    def attempt_resume(self, session_id: str) -> tuple[bool, WorkflowContext | None]:
        """Attempt to resume a halted workflow from last checkpoint."""
        resume_result = self._rc.resume(session_id)
        if not resume_result.resumed:
            return False, None

        now = datetime.now(timezone.utc)
        restored_context = resume_result.checkpoint.context_snapshot  # type: ignore[union-attr]

        self._ep.publish(WorkflowResumed(
            event_id=f"ev_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            workflow_id=restored_context.workflow_id,
            occurred_at=now,
            correlation_id=restored_context.execution_metadata.correlation_id,
            resumed_from_state=resume_result.from_state,  # type: ignore[arg-type]
            checkpoint_version=resume_result.checkpoint.checkpoint_version,  # type: ignore[union-attr]
        ))
        
        self._mc.record_checkpoint_restore(session_id)
        return True, restored_context


# ─── LlmAgent Instantiation ───────────────────────────────────────────────────

_config = _load_config()
_policies = _load_policies()
_system_instruction = (
    f"{_config['system_instruction']}\n\n=== SHARED POLICIES ===\n{_policies}"
)

# Instantiate the ADK LlmAgent.
agent = LlmAgent(
    name=_config["name"],
    model=_config["model"],
    instruction=_system_instruction,
    description=_config["description"],
    tools=[],  # Orchestrator has zero direct tools — routing authority only.
)
