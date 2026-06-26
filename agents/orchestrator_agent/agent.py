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
from .interfaces.checkpoint import CheckpointInterface, CheckpointProviderFactory
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
from .runtime_config import RuntimeConfig
from .preflight import PreflightValidator
from .circuit_breaker import CircuitBreakerRegistry
from .cache_layer import RuntimeCacheManager
from .runtime_services import RuntimeServices
from .mcp_lifecycle import MCPLifecycleManager
from .service_names import ServiceName

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

    def __init__(
        self,
        deps: OrchestratorDependencies,
        services: Optional[RuntimeServices] = None,
    ) -> None:
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

        if services is None:
            from .protocols import SystemClock
            from .preflight import PreflightValidator
            config = getattr(deps.failure_policy, "config", None) or RuntimeConfig.load_from_env()
            cache_mgr = RuntimeCacheManager(
                ttl_discovery=config.cache_ttl_discovery,
                ttl_audit=config.cache_ttl_audit,
            )
            cbr = getattr(deps.failure_policy, "cb_registry", None)
            if cbr is None:
                from .circuit_breaker import CircuitBreakerRegistry
                cbr = CircuitBreakerRegistry(
                    failure_threshold=config.circuit_breaker_failure_threshold,
                    cooldown_seconds=config.circuit_breaker_cooldown_seconds,
                    success_threshold=config.circuit_breaker_success_threshold,
                )
            
            services = RuntimeServices(
                config=config,
                cache_manager=cache_mgr,
                metrics_collector=deps.metrics_collector,
                cb_registry=cbr,
                failure_policy=deps.failure_policy,
                clock=SystemClock(),
                event_publisher=deps.event_publisher,
                audit_writer=deps.audit_writer,
                checkpoint_interface=deps.checkpoint_interface,
                worker_registry=deps.worker_registry,
                preflight_validator=PreflightValidator(config),
                mcp_lifecycle=MCPLifecycleManager(),
            )

        self.services = services
        self._executor = WorkflowExecutor(
            services=services,
            tc=self._tc,
            mg=self._mg,
            ev=self._ev,
            rc=self._rc,
        )

    @classmethod
    async def initialize(
        cls,
        config: Optional[RuntimeConfig] = None,
        bypass_preflight: bool = False,
    ) -> GrowthScoutOrchestrator:
        """
        Runs the 10-step startup lifecycle sequence:
        1. Load RuntimeConfig
        2. Validate RuntimeConfig
        3. Initialize shared clients
        4. Initialize caches
        5. Initialize metrics
        6. Initialize circuit breakers
        7. Execute preflight health checks
        8. Initialize WorkerRegistry
        9. Initialize GrowthScoutOrchestrator
        10. Accept workflow execution
        """
        # 1-2. Load and validate configuration
        cfg = config or RuntimeConfig.load_from_env()

        # 3. Initialize shared clients (mcp_lifecycle)
        mcp_lifecycle = MCPLifecycleManager()
        
        # 4. Initialize caches
        cache_manager = RuntimeCacheManager(
            ttl_discovery=cfg.cache_ttl_discovery,
            ttl_audit=cfg.cache_ttl_audit,
        )

        # 5. Initialize metrics
        metrics = InMemoryMetricsCollector()

        # 6. Initialize circuit breakers
        cb_registry = CircuitBreakerRegistry(
            failure_threshold=cfg.circuit_breaker_failure_threshold,
            cooldown_seconds=cfg.circuit_breaker_cooldown_seconds,
            success_threshold=cfg.circuit_breaker_success_threshold,
        )

        # 7. Execute preflight health checks
        validator = PreflightValidator(cfg)
        health_results = await validator.run_checks()
        has_downs = any(r.status == "DOWN" for r in health_results)
        if has_downs and not bypass_preflight:
            report = "\n".join(f"  - {r.component}: {r.status} ({r.message})" for r in health_results)
            raise RuntimeError(f"Startup halted due to failed preflight health checks:\n{report}")

        # 8. Initialize WorkerRegistry with runtime config
        worker_registry = WorkerRegistry(cfg)

        # 9. Initialize GrowthScoutOrchestrator
        failure_policy = FailurePolicy(config=cfg, cb_registry=cb_registry)

        from .protocols import SystemClock
        services = RuntimeServices(
            config=cfg,
            cache_manager=cache_manager,
            metrics_collector=metrics,
            cb_registry=cb_registry,
            failure_policy=failure_policy,
            clock=SystemClock(),
            event_publisher=StdoutEventPublisher(),
            audit_writer=AuditTrailWriter(),
            checkpoint_interface=CheckpointProviderFactory.create(cfg, cb_registry=cb_registry, metrics_collector=metrics),
            worker_registry=worker_registry,
            preflight_validator=validator,
            mcp_lifecycle=mcp_lifecycle,
        )

        deps = OrchestratorDependencies(
            worker_registry=worker_registry,
            failure_policy=failure_policy,
            metrics_collector=metrics,
            audit_writer=services.audit_writer,
            checkpoint_interface=services.checkpoint_interface,
            event_publisher=services.event_publisher,
        )

        orchestrator = cls(deps, services=services)

        # 10. Accept workflow execution
        return orchestrator

    # ─── Core coordination ────────────────────────────────────────────────────

    async def shutdown(self) -> None:
        """Shut down the orchestrator and all managed subprocesses."""
        if self.services and self.services.mcp_lifecycle:
            await self.services.mcp_lifecycle.shutdown_all()

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
        start_time = datetime.now(timezone.utc)
        recovery_id = f"rec_{uuid.uuid4().hex[:8]}"

        # Check Firestore circuit breaker if backend is firestore
        is_firestore = self.services.config.checkpoint_backend == "firestore"
        if is_firestore:
            cb = self.services.cb_registry.get_breaker(ServiceName.FIRESTORE)
            if not cb.allow_request():
                self._mc.record_failed_resumption(session_id)
                self._mc.record_service_request(session_id, ServiceName.FIRESTORE, "reject")
                
                # Emit WORKFLOW_RECOVERY_FAILED audit event
                entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=session_id,
                    workflow_id="unknown_wf",
                    event_type=AuditEventType.WORKFLOW_RECOVERY_FAILED,
                    workflow_state=WorkflowState.FAILED,
                    acting_agent="orchestrator_agent",
                    timestamp=datetime.now(timezone.utc),
                    input_references=[],
                    output_references=[],
                    transition_reason="Resumption aborted: Firestore circuit breaker is OPEN",
                    recovery_id=recovery_id,
                )
                self._aw.append(entry)
                return False, None

        try:
            resume_result = self._rc.resume(session_id)
            if not resume_result.resumed:
                self._mc.record_failed_resumption(session_id)
                entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=session_id,
                    workflow_id="unknown_wf",
                    event_type=AuditEventType.WORKFLOW_RECOVERY_FAILED,
                    workflow_state=WorkflowState.FAILED,
                    acting_agent="orchestrator_agent",
                    timestamp=datetime.now(timezone.utc),
                    input_references=[],
                    output_references=[],
                    transition_reason=f"Resumption denied: {resume_result.denial_reason}",
                    recovery_id=recovery_id,
                )
                self._aw.append(entry)
                return False, None

            now = datetime.now(timezone.utc)
            restored_context = resume_result.checkpoint.context_snapshot  # type: ignore[union-attr]
            
            # Attach recovery_id to the restored context
            restored_context = restored_context.model_copy(update={"recovery_id": recovery_id})

            # Record recovery metrics
            duration_ms = (now - start_time).total_seconds() * 1000.0
            self._mc.record_recovery_duration(session_id, duration_ms)
            self._mc.record_resumed_workflow(session_id)
            self._mc.record_checkpoint_restore(session_id)

            # Emit WORKFLOW_RESUMED audit event
            entry = AuditTrailEntry(
                entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                workflow_id=restored_context.workflow_id,
                event_type=AuditEventType.WORKFLOW_RESUMED,
                workflow_state=resume_result.from_state,  # type: ignore[arg-type]
                acting_agent="orchestrator_agent",
                timestamp=now,
                input_references=[],
                output_references=[],
                transition_reason=f"Workflow resumed from state {resume_result.from_state.value}",
                recovery_id=recovery_id,
            )
            self._aw.append(entry)

            self._ep.publish(WorkflowResumed(
                event_id=f"ev_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                workflow_id=restored_context.workflow_id,
                occurred_at=now,
                correlation_id=restored_context.execution_metadata.correlation_id,
                resumed_from_state=resume_result.from_state,  # type: ignore[arg-type]
                checkpoint_version=resume_result.checkpoint.checkpoint_version,  # type: ignore[union-attr]
            ))

            return True, restored_context

        except Exception as exc:
            self._mc.record_failed_resumption(session_id)
            entry = AuditTrailEntry(
                entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                workflow_id="unknown_wf",
                event_type=AuditEventType.WORKFLOW_RECOVERY_FAILED,
                workflow_state=WorkflowState.FAILED,
                acting_agent="orchestrator_agent",
                timestamp=datetime.now(timezone.utc),
                input_references=[],
                output_references=[],
                transition_reason=f"Resumption failed with exception: {str(exc)}",
                recovery_id=recovery_id,
            )
            self._aw.append(entry)
            raise exc


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
