# agents/orchestrator_agent/workflow_executor.py
"""
WorkflowExecutor component for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent
Responsibility: Runs the execution loop dynamically based on declarative StateNodes,
                manages TransitionPlans, StateResults, and ExecutionTraces.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type, Callable

from pydantic import BaseModel, Field

from .state_machine.states import WorkflowState, StateType, EvidenceRequirement, WORKFLOW_TOPOLOGY, TERMINAL_STATES
from .state_machine.workflow_context import WorkflowContext, EvidenceReference, PartitionSummary, WorkflowTimestamps
from .state_machine.transition_controller import TransitionController
from .state_machine.memory_governor import MemoryGovernor
from .hooks.evidence_validator import EvidenceValidationHook
from .hooks.audit_trail import AuditTrailWriter, AuditTrailEntry, AuditEventType
from .interfaces.checkpoint import CheckpointInterface, WorkflowCheckpoint, CURRENT_SCHEMA_VERSION, WORKFLOW_VERSION
from .interfaces.resumability import ResumabilityController
from .interfaces.events import (
    EventPublisher,
    StdoutEventPublisher,
    TransitionExecuted,
    CheckpointSaved,
    WorkerCompleted,
    WorkerFailed,
    WorkflowPaused,
    WorkflowResumed,
    MemoryWritten,
)
from .interfaces.worker_invocation import WorkerRegistry, WorkerInvocationRequest, WorkerInvocationResult, RetryPolicy, WorkerExecutionResult
from .failure_policy import FailurePolicy
from .metrics_collector import WorkflowMetricsCollector, InMemoryMetricsCollector
from .exceptions import InvalidTransitionError, EvidenceValidationError, WorkerInvocationError, CostThresholdExceededError, SchemaValidationError, BusinessValidationError
from .runtime_config import RuntimeConfig
from .circuit_breaker import CircuitState
from .service_names import ServiceName
from .cache_layer import RuntimeCacheManager
from .error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from .runtime_services import RuntimeServices
from .validators import ValidationPipeline

from agents.shared.schemas import (
    DiscoveryLead,
    DiscoveryLeadsSchema,
    AuditResultsSchema,
    OpportunityAnalysisSchema,
    GrowthReportsSchema,
)

# ─── Pydantic input models for workers ────────────────────────────────────────

class DiscoveryInput(BaseModel):
    niche: str
    location: str
    max_leads: int

class WebsiteAnalysisInput(BaseModel):
    website_url: str

class OpportunityAnalysisInput(BaseModel):
    website_leads: List[DiscoveryLead]
    no_website_leads: List[DiscoveryLead]
    audit_results: List[AuditResultsSchema]
    competitor_candidates: List[DiscoveryLead]

class GrowthReportInput(BaseModel):
    niche: str
    location: str
    opportunity_results: OpportunityAnalysisSchema
    reviewer_feedback: Optional[str] = None


# ─── TransitionPlan ───────────────────────────────────────────────────────────

class TransitionPlan(BaseModel):
    """
    Immutable plan defining a proposed state transition and context patch.
    """
    model_config = {"frozen": True}

    target_state: WorkflowState
    context_patch: Dict[str, Any] = Field(default_factory=dict)
    create_checkpoint: bool = True
    publish_events: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ─── StateResult ──────────────────────────────────────────────────────────────

class StateResult(BaseModel):
    """
    Typed result returned from executing a StateNode.
    """
    model_config = {"frozen": True}

    worker_output: Optional[BaseModel] = None
    evidence_generated: List[EvidenceReference] = Field(default_factory=list)
    metrics_delta: Dict[str, int] = Field(default_factory=dict)
    transition_plan: TransitionPlan
    execution_status: str


# ─── ExecutionTrace ───────────────────────────────────────────────────────────

class TraceEntry(BaseModel):
    """Single chronological trace entry."""
    model_config = {"frozen": True}

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str
    details: Dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    """In-memory trace timeline for execution debugging."""
    model_config = {"frozen": True}

    session_id: str
    workflow_id: str
    entries: List[TraceEntry] = Field(default_factory=list)

    def with_entry(self, entry: TraceEntry) -> ExecutionTrace:
        return self.model_copy(update={"entries": [*self.entries, entry]})


# ─── WorkflowExecutor ─────────────────────────────────────────────────────────

class WorkflowExecutor:
    """
    Execution engine managing DAG execution, HITL, retries, and traces.
    """

    def __init__(
        self,
        services: Optional[RuntimeServices] = None,
        tc: Optional[TransitionController] = None,
        wr: Optional[WorkerRegistry] = None,
        mg: Optional[MemoryGovernor] = None,
        ev: Optional[EvidenceValidationHook] = None,
        aw: Optional[AuditTrailWriter] = None,
        ci: Optional[CheckpointInterface] = None,
        ep: Optional[EventPublisher] = None,
        rc: Optional[ResumabilityController] = None,
        fp: Optional[FailurePolicy] = None,
        mc: Optional[WorkflowMetricsCollector] = None,
        config: Optional[RuntimeConfig] = None,
        cache_manager: Optional[RuntimeCacheManager] = None,
    ) -> None:
        if services is None:
            from .protocols import SystemClock
            from .preflight import PreflightValidator
            from .circuit_breaker import CircuitBreakerRegistry
            
            cfg = config or RuntimeConfig.load_from_env()
            cache_mgr = cache_manager or RuntimeCacheManager(
                ttl_discovery=cfg.cache_ttl_discovery,
                ttl_audit=cfg.cache_ttl_audit,
            )
            cbr = CircuitBreakerRegistry(
                failure_threshold=cfg.circuit_breaker_failure_threshold,
                cooldown_seconds=cfg.circuit_breaker_cooldown_seconds,
                success_threshold=cfg.circuit_breaker_success_threshold,
                state_transition_callback=self._on_circuit_breaker_transition,
            )
            fp_resolved = fp or FailurePolicy(config=cfg, cb_registry=cbr)
            
            services = RuntimeServices(
                config=cfg,
                cache_manager=cache_mgr,
                metrics_collector=mc or InMemoryMetricsCollector(),
                cb_registry=cbr,
                failure_policy=fp_resolved,
                clock=SystemClock(),
                event_publisher=ep or StdoutEventPublisher(),
                audit_writer=aw or AuditTrailWriter(),
                checkpoint_interface=ci or CheckpointInterface(),
                worker_registry=wr or WorkerRegistry(),
                preflight_validator=PreflightValidator(cfg),
            )

        self.services = services
        if services and services.cb_registry:
            services.cb_registry.state_transition_callback = self._on_circuit_breaker_transition
            for breaker in services.cb_registry._breakers.values():
                breaker.state_transition_callback = self._on_circuit_breaker_transition

        self._tc = tc or TransitionController()
        self._mg = mg or MemoryGovernor()
        self._ev = ev or EvidenceValidationHook()
        self._rc = rc or ResumabilityController(checkpoint_interface=services.checkpoint_interface)

        # Wire up executor fields from services
        self._config = services.config
        self._cache_manager = services.cache_manager
        self._mc = services.metrics_collector
        self._fp = services.failure_policy
        self._ep = services.event_publisher
        self._aw = services.audit_writer
        self._ci = services.checkpoint_interface
        self._wr = services.worker_registry
        
        self._traces: Dict[str, ExecutionTrace] = {}
        self._budgets: Dict[str, WorkflowRunBudget] = {}
        self._worker_timelines: Dict[str, List[WorkerExecutionResult]] = {}
        self._vp = ValidationPipeline()

        # Active session context tracking for CB callbacks and metrics recovery
        self._active_session_id = None
        self._active_workflow_id = None
        self._active_state = None
        self._active_recovery_id = None

        # Pluggable lifecycle hooks (worker-level)
        self.before_worker_hooks: List[Callable[[WorkerInvocationRequest], None]] = []
        self.after_worker_hooks: List[Callable[[WorkerInvocationRequest, WorkerInvocationResult], None]] = []
        self.validate_output_hooks: List[Callable[[str, BaseModel], None]] = []

        # Workflow-level lifecycle hooks
        self.before_workflow_hooks: List[Callable[[WorkflowContext], None]] = []
        self.after_workflow_hooks: List[Callable[[WorkflowContext], None]] = []
        self.before_state_hooks: List[Callable[[WorkflowContext], None]] = []
        self.after_state_hooks: List[Callable[[WorkflowContext], None]] = []
        self.before_transition_hooks: List[Callable[[WorkflowContext, TransitionPlan], None]] = []
        self.after_transition_hooks: List[Callable[[WorkflowContext, WorkflowContext], None]] = []

    def _on_circuit_breaker_transition(self, service_name: ServiceName, old_state: CircuitState, new_state: CircuitState) -> None:
        session_id = getattr(self, "_active_session_id", None)
        workflow_id = getattr(self, "_active_workflow_id", None)
        current_state = getattr(self, "_active_state", WorkflowState.IDLE)
        recovery_id = getattr(self, "_active_recovery_id", None)
        
        # Increment metrics
        if session_id:
            if new_state == CircuitState.OPEN:
                self._mc.record_circuit_breaker_open(session_id)
            elif new_state == CircuitState.HALF_OPEN:
                self._mc.record_circuit_breaker_half_open(session_id)
            elif new_state == CircuitState.CLOSED:
                self._mc.record_circuit_breaker_recovered(session_id)

            # Append audit events
            event_type = None
            if new_state == CircuitState.OPEN:
                event_type = AuditEventType.CIRCUIT_OPENED
            elif new_state == CircuitState.HALF_OPEN:
                event_type = AuditEventType.CIRCUIT_HALF_OPEN
            elif new_state == CircuitState.CLOSED:
                event_type = AuditEventType.CIRCUIT_CLOSED
                
            if event_type and workflow_id:
                entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=session_id,
                    workflow_id=workflow_id,
                    event_type=event_type,
                    workflow_state=current_state,
                    acting_agent="orchestrator_agent",
                    timestamp=self.services.clock.now_utc(),
                    input_references=[],
                    output_references=[],
                    transition_reason=f"Circuit breaker for {service_name.value} transitioned from {old_state.value} to {new_state.value}",
                    recovery_id=recovery_id,
                )
                self._aw.append(entry)

    def get_trace(self, session_id: str) -> Optional[ExecutionTrace]:
        """Retrieve trace for session."""
        return self._traces.get(session_id)

    def _add_trace_entry(self, session_id: str, workflow_id: str, event_type: str, details: Dict[str, Any]) -> None:
        trace = self._traces.get(session_id)
        if not trace:
            trace = ExecutionTrace(session_id=session_id, workflow_id=workflow_id)
        recovery_id = getattr(self, "_active_recovery_id", None)
        if recovery_id:
            details = {**details, "recovery_id": recovery_id}
        entry = TraceEntry(event_type=event_type, details=details)
        self._traces[session_id] = trace.with_entry(entry)

    async def execute_to_gate(self, context: WorkflowContext) -> WorkflowContext:
        """
        Run the execution loop until a HITL Gate or Terminal state is reached.
        """
        # Restore budget and timelines from context if present
        if context.budget is not None:
            if not hasattr(self, "_budgets"):
                self._budgets = {}
            self._budgets[context.session_id] = context.budget

        if context.worker_timeline:
            if not hasattr(self, "_worker_timelines"):
                self._worker_timelines = {}
            from .interfaces.worker_invocation import WorkerExecutionResult
            self._worker_timelines[context.session_id] = [
                WorkerExecutionResult.model_validate(res) if isinstance(res, dict) else res
                for res in context.worker_timeline
            ]

        if hasattr(context, "metrics") and context.metrics is not None:
            service_metrics = getattr(context, "service_metrics", None)
            self._mc.restore_metrics(context.session_id, context.metrics, service_metrics)

        for hook in self.before_workflow_hooks:
            try:
                hook(context)
            except Exception:
                pass

        start_time = self.services.clock.now_utc()
        curr = context
        self._add_trace_entry(curr.session_id, curr.workflow_id, "execution_started", {"start_state": curr.current_state.value})

        # Acquire MCP processes at start of execution
        mcp_lifecycle = self.services.mcp_lifecycle
        acquired = []
        import sys
        if mcp_lifecycle and self._config.google_maps_api_key and self._config.gemini_api_key:
            try:
                env = {
                    "GOOGLE_MAPS_API_KEY": self._config.google_maps_api_key,
                    "GEMINI_API_KEY": self._config.gemini_api_key,
                }
                # Enforce MCP pre-acquisition startup timeout
                await asyncio.wait_for(
                    mcp_lifecycle.acquire(
                        "local_search_server",
                        sys.executable,
                        ["-m", "servers.local_search_server.server"],
                        env
                    ),
                    timeout=self._config.mcp_timeout_seconds
                )
                acquired.append("local_search_server")
                await asyncio.wait_for(
                    mcp_lifecycle.acquire(
                        "web_analyzer_server",
                        sys.executable,
                        ["-m", "servers.web_analyzer_server.server"],
                        env
                    ),
                    timeout=self._config.mcp_timeout_seconds
                )
                acquired.append("web_analyzer_server")
            except Exception as e:
                self._add_trace_entry(context.session_id, context.workflow_id, "mcp_pre_acquisition_failed", {"error": str(e)})

        try:
            self._active_session_id = context.session_id
            self._active_workflow_id = context.workflow_id
            self._active_state = context.current_state
            self._active_recovery_id = getattr(context, "recovery_id", None)

            while True:
                node = WORKFLOW_TOPOLOGY[curr.current_state]

                # Check overall workflow timeout limit (checking elapsed time relative to budget start_time)
                budget = self._get_or_create_budget(curr.session_id)
                elapsed = (self.services.clock.now_utc() - budget.start_time).total_seconds()
                if elapsed > self._config.workflow_timeout_seconds:
                    self._mc.record_timeout(curr.session_id)
                    entry = AuditTrailEntry(
                        entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                        session_id=curr.session_id,
                        workflow_id=curr.workflow_id,
                        event_type=AuditEventType.TIMEOUT_OCCURRED,
                        workflow_state=curr.current_state,
                        acting_agent="orchestrator_agent",
                        timestamp=self.services.clock.now_utc(),
                        input_references=[],
                        output_references=[],
                        transition_reason=f"Workflow execution timeout occurred (limit: {self._config.workflow_timeout_seconds}s)",
                        recovery_id=getattr(curr, "recovery_id", None),
                    )
                    self._aw.append(entry)
                    plan = TransitionPlan(
                        target_state=WorkflowState.FAILED,
                        context_patch={},
                        create_checkpoint=True,
                        publish_events=True,
                        metadata={"reason": "Workflow timeout limit exceeded"}
                    )
                    curr = self._apply_transition_plan(curr, plan, "orchestrator_agent", "Workflow timeout limit exceeded")
                    break

                if curr.current_state in TERMINAL_STATES:
                    self._add_trace_entry(curr.session_id, curr.workflow_id, "terminal_status", {"state": curr.current_state.value})
                    self._mc.record_completion(curr.session_id, curr.current_state == WorkflowState.COMPLETED)
                    duration_ms = (self.services.clock.now_utc() - start_time).total_seconds() * 1000.0
                    self._mc.record_duration(curr.session_id, duration_ms)
                    break

                if node.state_type == StateType.HITL_GATE:
                    self._add_trace_entry(curr.session_id, curr.workflow_id, "hitl_gate_reached", {"state": curr.current_state.value})
                    break

                # Execute single step
                curr = await self.execute_step(curr)
        finally:
            self._active_session_id = None
            self._active_workflow_id = None
            self._active_state = None
            self._active_recovery_id = None

            if mcp_lifecycle:
                for srv in acquired:
                    try:
                        await mcp_lifecycle.release(srv)
                    except Exception as e:
                        self._add_trace_entry(context.session_id, context.workflow_id, "mcp_release_failed", {"server": srv, "error": str(e)})

        for hook in self.after_workflow_hooks:
            try:
                hook(curr)
            except Exception:
                pass

        return curr

    async def execute_step(self, context: WorkflowContext) -> WorkflowContext:
        """
        Execute a single workflow node dynamically.
        """
        # Restore budget, timelines, and metrics from context if present
        if context.budget is not None:
            if not hasattr(self, "_budgets"):
                self._budgets = {}
            self._budgets[context.session_id] = context.budget

        if context.worker_timeline:
            if not hasattr(self, "_worker_timelines"):
                self._worker_timelines = {}
            from .interfaces.worker_invocation import WorkerExecutionResult
            self._worker_timelines[context.session_id] = [
                WorkerExecutionResult.model_validate(res) if isinstance(res, dict) else res
                for res in context.worker_timeline
            ]

        if hasattr(context, "metrics") and context.metrics is not None:
            service_metrics = getattr(context, "service_metrics", None)
            self._mc.restore_metrics(context.session_id, context.metrics, service_metrics)

        self._active_session_id = context.session_id
        self._active_workflow_id = context.workflow_id
        self._active_state = context.current_state
        self._active_recovery_id = getattr(context, "recovery_id", None)

        # Check overall workflow timeout limit
        budget = self._get_or_create_budget(context.session_id)
        elapsed = (self.services.clock.now_utc() - budget.start_time).total_seconds()
        if elapsed > self._config.workflow_timeout_seconds:
            self._mc.record_timeout(context.session_id)
            entry = AuditTrailEntry(
                entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                session_id=context.session_id,
                workflow_id=context.workflow_id,
                event_type=AuditEventType.TIMEOUT_OCCURRED,
                workflow_state=context.current_state,
                acting_agent="orchestrator_agent",
                timestamp=self.services.clock.now_utc(),
                input_references=[],
                output_references=[],
                transition_reason=f"Workflow execution timeout occurred (limit: {self._config.workflow_timeout_seconds}s)",
                recovery_id=getattr(context, "recovery_id", None),
            )
            self._aw.append(entry)
            plan = TransitionPlan(
                target_state=WorkflowState.FAILED,
                context_patch={},
                create_checkpoint=True,
                publish_events=True,
                metadata={"reason": "Workflow timeout limit exceeded"}
            )
            return self._apply_transition_plan(context, plan, "orchestrator_agent", "Workflow timeout limit exceeded")

        try:
            for hook in self.before_state_hooks:
                try:
                    hook(context)
                except Exception:
                    pass

            node = WORKFLOW_TOPOLOGY[context.current_state]
            self._add_trace_entry(context.session_id, context.workflow_id, "state_entered", {"state": context.current_state.value})

            if node.state_type == StateType.START:
                # Transition IDLE -> DISCOVERING
                plan = TransitionPlan(
                    target_state=node.default_next_state,  # DISCOVERING
                    create_checkpoint=True,
                    publish_events=True,
                )
                result_context = self._apply_transition_plan(context, plan, "orchestrator_agent", "Start pipeline")

            elif node.state_type == StateType.PARTITION_NODE:
                # LEAD_PARTITIONING logic
                result_context = await self._execute_partitioning(context)

            elif node.state_type == StateType.AGENT_NODE:
                result_context = await self._execute_agent_node(context)

            else:
                # Fallback for unexpected nodes
                result_context = context

            for hook in self.after_state_hooks:
                try:
                    hook(result_context)
                except Exception:
                    pass

            return result_context
        finally:
            self._active_session_id = None
            self._active_workflow_id = None
            self._active_state = None
            self._active_recovery_id = None

    async def _execute_partitioning(self, context: WorkflowContext) -> WorkflowContext:
        now = self.services.clock.now_utc()
        leads = context.discovery_results.leads if context.discovery_results else []

        website_leads = [
            lead for lead in leads
            if lead.website_url is not None and lead.website_url != "" and lead.website_status != "No Website"
        ]
        no_website_leads = [lead for lead in leads if lead not in website_leads]

        total_discovered = len(leads)
        total_partitioned = len(website_leads) + len(no_website_leads)

        # Integrity Validation Check
        if total_partitioned != total_discovered:
            self._add_trace_entry(context.session_id, context.workflow_id, "validation_outcome", {
                "validator": "partition_integrity",
                "success": False,
                "details": f"Discovered leads {total_discovered} != partitioned leads {total_partitioned}"
            })
            plan = TransitionPlan(
                target_state=WorkflowState.FAILED,
                context_patch={},
                create_checkpoint=True,
                publish_events=True,
                metadata={"reason": "lead_partition_integrity_failure"}
            )
            return self._apply_transition_plan(context, plan, "orchestrator_agent", "Partition integrity validation failure")

        self._add_trace_entry(context.session_id, context.workflow_id, "validation_outcome", {
            "validator": "partition_integrity",
            "success": True,
            "website_leads": len(website_leads),
            "no_website_leads": len(no_website_leads)
        })

        summary = PartitionSummary(
            total_leads=total_discovered,
            website_leads=len(website_leads),
            no_website_leads=len(no_website_leads),
            integrity_valid=True
        )

        # Transition logic from LEAD_PARTITIONING
        if len(website_leads) > 0:
            target = WorkflowState.AUDITING
            reason = "Website leads present. Initiating crawler audits."
        else:
            target = WorkflowState.OPPORTUNITY_ANALYSIS
            reason = "No leads with websites found. Skipping Auditing."

        plan = TransitionPlan(
            target_state=target,
            context_patch={"partition_summary": summary},
            create_checkpoint=True,
            publish_events=True
        )
        return self._apply_transition_plan(context, plan, "orchestrator_agent", reason)

    async def _execute_agent_node(self, context: WorkflowContext) -> WorkflowContext:
        node = WORKFLOW_TOPOLOGY[context.current_state]
        worker_name = node.owner_agent
        assert worker_name is not None

        if worker_name == "business_discovery_agent":
            # Invoke business discovery
            input_payload = DiscoveryInput(
                niche=context.workflow_metadata.niche,
                location=context.workflow_metadata.location,
                max_leads=context.workflow_metadata.max_leads
            )
            res = await self._invoke_worker_with_retry(context, worker_name, input_payload, DiscoveryLeadsSchema)
            if not res.success:
                return self._handle_worker_fatal_failure(context, worker_name, res.error_message or "Unknown failure")

            # Logical/Business Verification check
            discovery_leads = res.output
            assert isinstance(discovery_leads, DiscoveryLeadsSchema)

            # Transition determination
            target = WorkflowState.LEAD_PARTITIONING if len(discovery_leads.leads) > 0 else WorkflowState.NO_LEADS_FOUND
            reason = "Discovered local leads" if len(discovery_leads.leads) > 0 else "No leads found matching query"

            plan = TransitionPlan(
                target_state=target,
                context_patch={"discovery_results": discovery_leads},
                create_checkpoint=True,
                publish_events=True
            )
            return self._apply_transition_plan(context, plan, "orchestrator_agent", reason)

        elif worker_name == "website_analysis_agent":
            # Run sequential website crawls
            leads = context.discovery_results.leads if context.discovery_results else []
            website_leads = [
                lead for lead in leads
                if lead.website_url is not None and lead.website_url != "" and lead.website_status != "No Website"
            ]

            audit_results_list = []
            success_count = 0

            for lead in website_leads:
                # Prepare single analysis input
                input_payload = WebsiteAnalysisInput(website_url=lead.website_url)
                res = await self._invoke_worker_with_retry(context, worker_name, input_payload, AuditResultsSchema)
                if res.success and res.output:
                    audit_results_list.append(res.output)
                    success_count += 1
                else:
                    if "circuit breaker" in (res.error_message or "").lower() or "auth" in (res.error_message or "").lower():
                        return self._handle_worker_fatal_failure(context, worker_name, res.error_message or "Fatal infrastructure failure")
                    # Concurrency isolate failures: we proceed despite single crawler error
                    self._add_trace_entry(context.session_id, context.workflow_id, "crawler_failed", {"url": lead.website_url, "error": res.error_message})

            # Check min crawler success rate: success_count / total website leads
            success_rate = (success_count / len(website_leads)) if len(website_leads) > 0 else 1.0
            self._add_trace_entry(context.session_id, context.workflow_id, "crawling_summary", {"success_rate": success_rate})

            plan = TransitionPlan(
                target_state=node.default_next_state,  # OPPORTUNITY_ANALYSIS
                context_patch={"audit_results": audit_results_list},
                create_checkpoint=True,
                publish_events=True
            )
            return self._apply_transition_plan(context, plan, "orchestrator_agent", "Website auditing completed.")

        elif worker_name == "opportunity_agent":
            leads = context.discovery_results.leads if context.discovery_results else []
            website_leads = [lead for lead in leads if lead.website_url]
            no_website_leads = [lead for lead in leads if not lead.website_url]
            competitors = context.discovery_results.competitor_candidates if context.discovery_results else []

            input_payload = OpportunityAnalysisInput(
                website_leads=website_leads,
                no_website_leads=no_website_leads,
                audit_results=context.audit_results,
                competitor_candidates=competitors
            )
            res = await self._invoke_worker_with_retry(context, worker_name, input_payload, OpportunityAnalysisSchema)
            if not res.success:
                return self._handle_worker_fatal_failure(context, worker_name, res.error_message or "Unknown failure")

            opp_output = res.output
            assert isinstance(opp_output, OpportunityAnalysisSchema)

            # Scenario 13: Logical Validation check on lead_score / category scores
            logical_valid = True
            invalid_details = ""
            if opp_output.lead_score < 0 or opp_output.lead_score > 100:
                logical_valid = False
                invalid_details = f"lead_score {opp_output.lead_score} is outside range [0, 100]."

            # Check specific CategoryScores ranges
            scores = opp_output.opportunity_scores
            for field_name in ["no_website", "website_modernization", "seo", "performance", "conversion_optimization", "analytics", "reputation", "competitive_positioning"]:
                val = getattr(scores, field_name)
                if val is not None and (val < 0 or val > 100):
                    logical_valid = False
                    invalid_details = f"category score {field_name}={val} is outside range [0, 100]."

            if not logical_valid:
                self._add_trace_entry(context.session_id, context.workflow_id, "validation_outcome", {
                    "validator": "business_logic",
                    "success": False,
                    "details": invalid_details
                })
                plan = TransitionPlan(
                    target_state=WorkflowState.FAILED,
                    context_patch={},
                    create_checkpoint=True,
                    publish_events=True,
                    metadata={"reason": "logical_validation_failure"}
                )
                return self._apply_transition_plan(context, plan, "orchestrator_agent", f"Logical business validation failed: {invalid_details}")

            self._add_trace_entry(context.session_id, context.workflow_id, "validation_outcome", {
                "validator": "business_logic",
                "success": True
            })

            plan = TransitionPlan(
                target_state=node.default_next_state,  # REPORT_GENERATION
                context_patch={"opportunity_results": opp_output},
                create_checkpoint=True,
                publish_events=True
            )
            return self._apply_transition_plan(context, plan, "orchestrator_agent", "Opportunities classified and scored.")

        elif worker_name == "growth_intelligence_agent":
            # Retrieve human feedback if loop is on re-generation
            feedback = None
            # Find in audit trail or metadata
            feedback_entries = self._aw.find_by_event_type(context.session_id, AuditEventType.VALIDATION_FAILED)
            if feedback_entries:
                feedback = feedback_entries[-1].transition_reason

            assert context.opportunity_results is not None
            input_payload = GrowthReportInput(
                niche=context.workflow_metadata.niche,
                location=context.workflow_metadata.location,
                opportunity_results=context.opportunity_results,
                reviewer_feedback=feedback
            )
            res = await self._invoke_worker_with_retry(context, worker_name, input_payload, GrowthReportsSchema)
            if not res.success:
                return self._handle_worker_fatal_failure(context, worker_name, res.error_message or "Unknown failure")

            report_output = res.output
            assert isinstance(report_output, GrowthReportsSchema)

            plan = TransitionPlan(
                target_state=node.default_next_state,  # AWAITING_APPROVAL
                context_patch={"growth_report": report_output},
                create_checkpoint=True,
                publish_events=True
            )
            return self._apply_transition_plan(context, plan, "orchestrator_agent", "Growth report compiled.")

        return context

    def _handle_worker_fatal_failure(self, context: WorkflowContext, worker_name: str, message: str) -> WorkflowContext:
        plan = TransitionPlan(
            target_state=WorkflowState.FAILED,
            context_patch={},
            create_checkpoint=True,
            publish_events=True,
            metadata={"reason": f"Worker {worker_name} failed fatally: {message}"}
        )
        return self._apply_transition_plan(context, plan, "orchestrator_agent", f"Worker fatal failure: {message}")

    async def _invoke_worker_with_retry(
        self,
        context: WorkflowContext,
        worker_name: str,
        input_payload: BaseModel,
        output_schema: Type[BaseModel],
    ) -> WorkerInvocationResult:
        correlation_id = context.execution_metadata.correlation_id

        # Cache hit check
        cached_val = None
        cache_key = ""
        if worker_name == "business_discovery_agent":
            niche = getattr(input_payload, "niche", "")
            location = getattr(input_payload, "location", "")
            cache_key = f"{niche} @ {location}"
            cached_val = self._cache_manager.discovery.get(cache_key)
        elif worker_name == "website_analysis_agent":
            url = getattr(input_payload, "website_url", "")
            cache_key = url
            cached_val = self._cache_manager.audit.get(cache_key)

        if cached_val is not None:
            self._add_trace_entry(context.session_id, context.workflow_id, "cache_hit", {
                "worker_name": worker_name,
                "key": cache_key,
                "correlation_id": correlation_id
            })
            result = WorkerInvocationResult(
                worker_name=worker_name,
                correlation_id=correlation_id,
                success=True,
                output=cached_val,
                execution_duration_ms=0.0,
                retries_attempted=0
            )
            self._record_worker_execution_result(context, result)
            return result

        request = WorkerInvocationRequest(
            worker_name=worker_name,
            input_payload=input_payload,
            expected_output_schema=output_schema.__name__,
            correlation_id=correlation_id,
            timeout=self._config.worker_timeout_seconds,
            retry_limit=self._config.max_retries,
        )

        attempts_made = 0
        self._add_trace_entry(context.session_id, context.workflow_id, "worker_invoked", {
            "worker_name": worker_name,
            "correlation_id": correlation_id
        })

        while True:
            attempts_made += 1
            self._mc.record_worker_execution(context.session_id, worker_name)

             # Trigger before_worker lifecycle hooks
            for hook in self.before_worker_hooks:
                try:
                    hook(request)
                except Exception:
                    pass

            start_time = self.services.clock.now_utc()
            try:
                # Check Circuit Breakers before execution
                self._fp.check_circuit_breakers(worker_name, correlation_id)

                # Resolve LlmAgent via registry
                agent_instance = self._wr.get(worker_name)
                
                # Emit VALIDATION_STARTED audit event
                val_start_time = self.services.clock.now_utc()
                validation_started_entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    event_type=AuditEventType.VALIDATION_STARTED,
                    workflow_state=context.current_state,
                    acting_agent=worker_name,
                    timestamp=val_start_time,
                    input_references=[],
                    output_references=[],
                    transition_reason=f"Validation pipeline started for worker {worker_name}",
                    partition_summary=context.partition_summary,
                )
                self._aw.append(validation_started_entry)

                # Dynamic model call or mock call
                out = await self._execute_agent_run(agent_instance, request, output_schema)

                try:
                    # Run central ValidationPipeline
                    val_res = self._vp.validate(worker_name, out, output_schema)
                except Exception as parse_err:
                    if isinstance(parse_err, (SchemaValidationError, BusinessValidationError)):
                        raise parse_err
                    val_duration_ms = (self.services.clock.now_utc() - val_start_time).total_seconds() * 1000.0
                    self._mc.record_validation(
                        session_id=context.session_id,
                        worker_name=worker_name,
                        validator_name="SchemaValidator",
                        duration_ms=val_duration_ms,
                        success=False,
                        failure_type="schema",
                        warnings_count=0,
                        normalized=False,
                    )
                    
                    schema_failed_entry = AuditTrailEntry(
                        entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                        session_id=context.session_id,
                        workflow_id=context.workflow_id,
                        event_type=AuditEventType.SCHEMA_VALIDATION_FAILED,
                        workflow_state=context.current_state,
                        acting_agent=worker_name,
                        timestamp=self.services.clock.now_utc(),
                        input_references=[],
                        output_references=[],
                        transition_reason=f"Schema validation failed: {str(parse_err)}",
                        partition_summary=context.partition_summary,
                    )
                    self._aw.append(schema_failed_entry)
                    raise SchemaValidationError(f"Schema validation failed: {str(parse_err)}", errors=[str(parse_err)])

                # Record validation metrics from pipeline
                self._mc.record_validation(
                    session_id=context.session_id,
                    worker_name=worker_name,
                    validator_name=val_res.metrics["validator_name"],
                    duration_ms=val_res.metrics["validation_duration_ms"],
                    success=val_res.valid,
                    failure_type=val_res.metrics["failure_type"],
                    warnings_count=val_res.metrics["warnings_count"],
                    normalized=val_res.metrics["normalized"],
                )

                if not val_res.valid:
                    self._add_trace_entry(context.session_id, context.workflow_id, "validation_outcome", {
                        "validator": "business_logic",
                        "success": False,
                        "details": f"Validation failed: {', '.join(val_res.errors)}"
                    })
                    failure_type = val_res.metrics["failure_type"]
                    if failure_type == "schema":
                        audit_event_type = AuditEventType.SCHEMA_VALIDATION_FAILED
                        exc_cls = SchemaValidationError
                    else:
                        audit_event_type = AuditEventType.BUSINESS_VALIDATION_FAILED
                        exc_cls = BusinessValidationError

                    validation_failed_entry = AuditTrailEntry(
                        entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                        session_id=context.session_id,
                        workflow_id=context.workflow_id,
                        event_type=audit_event_type,
                        workflow_state=context.current_state,
                        acting_agent=worker_name,
                        timestamp=self.services.clock.now_utc(),
                        input_references=[],
                        output_references=[],
                        transition_reason=f"Validation failed: {', '.join(val_res.errors)}",
                        partition_summary=context.partition_summary,
                    )
                    self._aw.append(validation_failed_entry)
                    raise exc_cls(f"Validation failed: {val_res.errors}", errors=val_res.errors)

                # Successful validation
                out = val_res.normalized_output
                self._add_trace_entry(context.session_id, context.workflow_id, "validation_outcome", {
                    "validator": "business_logic",
                    "success": True
                })

                # Record output normalized and validation succeeded audit events
                output_normalized_entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    event_type=AuditEventType.OUTPUT_NORMALIZED,
                    workflow_state=context.current_state,
                    acting_agent=worker_name,
                    timestamp=self.services.clock.now_utc(),
                    input_references=[],
                    output_references=[],
                    transition_reason=f"Output normalized for {worker_name}",
                    partition_summary=context.partition_summary,
                )
                self._aw.append(output_normalized_entry)

                validation_succeeded_entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    event_type=AuditEventType.VALIDATION_SUCCEEDED,
                    workflow_state=context.current_state,
                    acting_agent=worker_name,
                    timestamp=self.services.clock.now_utc(),
                    input_references=[],
                    output_references=[],
                    transition_reason=f"Validation succeeded for {worker_name}",
                    partition_summary=context.partition_summary,
                )
                self._aw.append(validation_succeeded_entry)

                # Validate Output hooks
                for v_hook in self.validate_output_hooks:
                    try:
                        v_hook(worker_name, out)
                    except Exception:
                        pass

                # Record success on circuit breaker
                self._fp.record_success(worker_name)
                # Record service requests metrics
                service = self._fp.get_service_for_worker(worker_name)
                self._mc.record_service_request(context.session_id, ServiceName.GEMINI, "success")
                if service != ServiceName.GEMINI:
                    self._mc.record_service_request(context.session_id, service, "success")

                # If attempts_made > 1, this means it completed after retrying!
                if attempts_made > 1:
                    retry_comp_entry = AuditTrailEntry(
                        entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                        session_id=context.session_id,
                        workflow_id=context.workflow_id,
                        event_type=AuditEventType.RETRY_COMPLETED,
                        workflow_state=context.current_state,
                        acting_agent=worker_name,
                        timestamp=self.services.clock.now_utc(),
                        input_references=[],
                        output_references=[],
                        transition_reason=f"Retry completed successfully for worker {worker_name} on attempt {attempts_made}",
                        recovery_id=getattr(context, "recovery_id", None),
                    )
                    self._aw.append(retry_comp_entry)

                # Populate Cache on success
                if worker_name == "business_discovery_agent" and cache_key:
                    self._cache_manager.discovery.set(cache_key, out)
                elif worker_name == "website_analysis_agent" and cache_key:
                    self._cache_manager.audit.set(cache_key, out)

                duration = (self.services.clock.now_utc() - start_time).total_seconds() * 1000.0
                self._mc.record_latency(context.session_id, worker_name, duration)

                result = WorkerInvocationResult(
                    worker_name=worker_name,
                    correlation_id=correlation_id,
                    success=True,
                    output=out,
                    execution_duration_ms=duration,
                    retries_attempted=attempts_made - 1,
                    warnings=val_res.warnings
                )

                # Trigger after_worker lifecycle hooks
                for hook in self.after_worker_hooks:
                    try:
                        hook(request, result)
                    except Exception:
                        pass

                self._ep.publish(WorkerCompleted(
                    event_id=f"ev_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    occurred_at=self.services.clock.now_utc(),
                    correlation_id=correlation_id,
                    worker_name=worker_name,
                    output_schema=output_schema.__name__,
                    duration_ms=duration
                ))

                self._record_worker_execution_result(context, result)
                return result

            except Exception as e:
                # Classify exception into GrowthScoutRuntimeError
                if isinstance(e, GrowthScoutRuntimeError):
                    runtime_error = e
                else:
                    service = self._fp.get_service_for_worker(worker_name)
                    err_code = RuntimeErrorCode.UNEXPECTED_ERROR
                    retryable = True
                    
                    if isinstance(e, SchemaValidationError):
                        err_code = RuntimeErrorCode.VALIDATION_ERROR
                        retryable = False
                    elif isinstance(e, BusinessValidationError):
                        err_code = RuntimeErrorCode.VALIDATION_ERROR
                        retryable = False
                    elif isinstance(e, asyncio.TimeoutError):
                        err_code = RuntimeErrorCode.TIMEOUT
                        retryable = True
                        self._mc.record_timeout(context.session_id)
                        # Append TIMEOUT_OCCURRED audit event
                        entry = AuditTrailEntry(
                            entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                            session_id=context.session_id,
                            workflow_id=context.workflow_id,
                            event_type=AuditEventType.TIMEOUT_OCCURRED,
                            workflow_state=context.current_state,
                            acting_agent=worker_name,
                            timestamp=self.services.clock.now_utc(),
                            input_references=[],
                            output_references=[],
                            transition_reason=f"Timeout occurred during worker {worker_name} execution (limit: {request.timeout}s)",
                            recovery_id=getattr(context, "recovery_id", None),
                        )
                        self._aw.append(entry)
                    elif "auth" in str(e).lower() or "api key" in str(e).lower() or "unauthorized" in str(e).lower():
                        err_code = RuntimeErrorCode.AUTH_ERROR
                        retryable = False
                    elif "rate limit" in str(e).lower() or "quota" in str(e).lower() or "429" in str(e).lower():
                        err_code = RuntimeErrorCode.RATE_LIMIT
                        retryable = True
                    elif "connection" in str(e).lower() or "network" in str(e).lower() or "dns" in str(e).lower():
                        err_code = RuntimeErrorCode.NETWORK_ERROR
                        retryable = True
                    elif isinstance(e, ValueError):
                        err_code = RuntimeErrorCode.VALIDATION_ERROR
                        retryable = False
                        
                    runtime_error = GrowthScoutRuntimeError(
                        error_code=err_code,
                        message=str(e),
                        service=service,
                        retryable=retryable,
                        correlation_id=correlation_id,
                        original_exception=e,
                    )

                # Record service request metrics & circuit breaker updates
                service = self._fp.get_service_for_worker(worker_name)
                if runtime_error.error_code == RuntimeErrorCode.CIRCUIT_BREAKER_OPEN:
                    self._mc.record_service_request(context.session_id, runtime_error.service or ServiceName.GEMINI, "reject")
                else:
                    self._fp.record_failure(worker_name, runtime_error)
                    self._mc.record_service_request(context.session_id, ServiceName.GEMINI, "failure")
                    if service != ServiceName.GEMINI:
                        self._mc.record_service_request(context.session_id, service, "failure")

                duration = (self.services.clock.now_utc() - start_time).total_seconds() * 1000.0
                self._mc.record_latency(context.session_id, f"{worker_name}_error", duration)

                result = WorkerInvocationResult(
                    worker_name=worker_name,
                    correlation_id=correlation_id,
                    success=False,
                    error_message=runtime_error.message,
                    execution_duration_ms=duration,
                    retries_attempted=attempts_made - 1
                )

                # Check if failure policy permits retry
                if self._fp.should_retry(request, attempts_made, runtime_error):
                    self._mc.record_worker_retry(context.session_id, worker_name)
                    self._mc.record_retry_attempt(context.session_id)
                    delay = self._fp.get_retry_delay(request, attempts_made)
                    
                    # Log RETRY_STARTED audit event
                    retry_start_entry = AuditTrailEntry(
                        entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                        session_id=context.session_id,
                        workflow_id=context.workflow_id,
                        event_type=AuditEventType.RETRY_STARTED,
                        workflow_state=context.current_state,
                        acting_agent=worker_name,
                        timestamp=self.services.clock.now_utc(),
                        input_references=[],
                        output_references=[],
                        transition_reason=f"Retry {attempts_made} started for worker {worker_name} after error: {runtime_error.message}",
                        recovery_id=getattr(context, "recovery_id", None),
                    )
                    self._aw.append(retry_start_entry)

                    self._add_trace_entry(context.session_id, context.workflow_id, "worker_retry", {
                        "worker_name": worker_name,
                        "attempt": attempts_made,
                        "delay_seconds": delay,
                        "reason": runtime_error.message,
                        "error_code": runtime_error.error_code.value,
                        "recovery_id": getattr(context, "recovery_id", None),
                    })
                    await asyncio.sleep(delay)
                    continue

                # Run hooks on failure
                for hook in self.after_worker_hooks:
                    try:
                        hook(request, result)
                    except Exception:
                        pass

                self._mc.record_worker_failure(context.session_id, worker_name)
                self._ep.publish(WorkerFailed(
                    event_id=f"ev_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    occurred_at=self.services.clock.now_utc(),
                    correlation_id=correlation_id,
                    worker_name=worker_name,
                    error_message=runtime_error.message,
                    retries_made=attempts_made
                ))

                self._record_worker_execution_result(context, result)
                return result

    def _get_or_create_budget(self, session_id: str) -> WorkflowRunBudget:
        if not hasattr(self, "_budgets"):
            self._budgets = {}
        if session_id not in self._budgets:
            from .run_budget import WorkflowRunBudget
            self._budgets[session_id] = WorkflowRunBudget(
                max_gemini_requests=self._config.max_gemini_requests,
                max_maps_requests=self._config.max_maps_requests,
                max_pages_crawled=self._config.max_pages_crawled,
                max_elapsed_seconds=self._config.max_elapsed_seconds,
                max_cost_limit=self._config.max_cost_limit,
                gemini_cost_per_request=self._config.gemini_cost_per_request,
                maps_cost_per_request=self._config.maps_cost_per_request,
                pages_cost_per_request=self._config.pages_cost_per_request,
            )
        return self._budgets[session_id]

    def _record_worker_execution_result(self, context: WorkflowContext, result: WorkerInvocationResult) -> None:
        if not hasattr(self, "_worker_timelines"):
            self._worker_timelines = {}
        
        # Populate metrics from budget
        metrics = {}
        if context.session_id in getattr(self, "_budgets", {}):
            b = self._budgets[context.session_id]
            metrics = {
                "gemini_requests": b.gemini_requests,
                "maps_requests": b.maps_requests,
                "pages_crawled": b.pages_crawled,
                "estimated_cost": b.estimated_cost,
            }
        
        # Extract evidence if any
        evidence = []
        if result.success and result.output:
            # Check for attributes like leads, opportunities, etc.
            if hasattr(result.output, "leads"):
                leads = getattr(result.output, "leads", [])
                if isinstance(leads, list):
                    evidence = [lead.model_dump() if hasattr(lead, "model_dump") else lead for lead in leads]
            elif hasattr(result.output, "audit_results"):
                audits = getattr(result.output, "audit_results", [])
                if isinstance(audits, list):
                    evidence = [audit.model_dump() if hasattr(audit, "model_dump") else audit for audit in audits]
            elif hasattr(result.output, "opportunities"):
                opps = getattr(result.output, "opportunities", [])
                if isinstance(opps, list):
                    evidence = [opp.model_dump() if hasattr(opp, "model_dump") else opp for opp in opps]
            elif hasattr(result.output, "growth_reports"):
                reports = getattr(result.output, "growth_reports", [])
                if isinstance(reports, list):
                    evidence = [rep.model_dump() if hasattr(rep, "model_dump") else rep for rep in reports]

        from .interfaces.worker_invocation import WorkerExecutionResult
        exec_res = WorkerExecutionResult(
            success=result.success,
            worker_name=result.worker_name,
            output=result.output,
            metrics=metrics,
            evidence=evidence,
            runtime=result.execution_duration_ms / 1000.0,
            retries=result.retries_attempted,
            warnings=getattr(result, "warnings", []),
            correlation_id=result.correlation_id,
        )

        if context.session_id not in self._worker_timelines:
            self._worker_timelines[context.session_id] = []
        self._worker_timelines[context.session_id].append(exec_res)

        self._add_trace_entry(
            context.session_id,
            context.workflow_id,
            "worker_timeline",
            {
                "worker_name": exec_res.worker_name,
                "success": exec_res.success,
                "runtime": exec_res.runtime,
                "retries": exec_res.retries,
                "correlation_id": exec_res.correlation_id,
                "metrics": exec_res.metrics,
            }
        )

    async def _execute_agent_run(
        self,
        agent_instance: Any,
        request: WorkerInvocationRequest,
        output_schema: Type[BaseModel],
        session_id: Optional[str] = None,
    ) -> BaseModel:
        # Standard InMemoryRunner execution or direct mock call if mock injected
        # Check if agent has a mocked run_async/before_tool_callback or is mocked in tests
        # We can construct ADK run
        from google.adk.apps import App
        from google.adk.runners import InMemoryRunner
        from google.genai import types
        import os
        import sys
        from unittest.mock import patch
        from contextlib import asynccontextmanager

        # Wire live credentials/keys from config to environment
        if self._config.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = self._config.gemini_api_key
        if self._config.google_maps_api_key:
            os.environ["GOOGLE_MAPS_API_KEY"] = self._config.google_maps_api_key

        if session_id:
            # Check and record Gemini request before model invocation
            budget = self._get_or_create_budget(session_id)
            if not budget.can_continue("gemini"):
                raise CostThresholdExceededError(
                    f"Gemini requests budget exceeded: {budget.gemini_requests}/{budget.max_gemini_requests}"
                )
            budget.record_operation("gemini")

            # Wrap tool callback to intercept and enforce budget on tools
            if not hasattr(agent_instance, "_original_before_tool_callback"):
                agent_instance._original_before_tool_callback = getattr(agent_instance, "before_tool_callback", None)

            original_callback = agent_instance._original_before_tool_callback

            async def intercepting_tool_callback(tool, args, tool_context=None):
                op_type = None
                if tool.name == "local_business_search":
                    op_type = "maps"
                elif tool.name in ["web_page_fetcher", "tech_footprint_scanner", "seo_auditor"]:
                    op_type = "scraper"

                if op_type:
                    # Check tool budget
                    if not budget.can_continue(op_type):
                        raise CostThresholdExceededError(
                            f"Budget exceeded for operation '{op_type}'"
                        )
                    # Check next Gemini request budget (processing tool output requires a model call)
                    if not budget.can_continue("gemini"):
                        raise CostThresholdExceededError(
                            f"Gemini requests budget exceeded for processing tool output"
                        )
                    
                    # Record both operations
                    budget.record_operation(op_type)
                    budget.record_operation("gemini")

                if original_callback:
                    try:
                        return await original_callback(tool, args, tool_context)
                    except TypeError:
                        return await original_callback(tool, args)
                return None

            agent_instance.before_tool_callback = intercepting_tool_callback

        app = App(name=agent_instance.name, root_agent=agent_instance)
        runner = InMemoryRunner(app=app)
        session = await runner.session_service.create_session(
            app_name=agent_instance.name, user_id="orchestrator"
        )
        
        prompt = f"Perform {agent_instance.name} tasks using input: {request.input_payload.model_dump_json()}"
        structured_output = None

        async def _run():
            nonlocal structured_output
            async for event in runner.run_async(
                user_id="orchestrator",
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
            ):
                if event.output is not None:
                    structured_output = event.output
            return structured_output

        # Setup custom stdio_client interceptor using mcp_lifecycle
        mcp_lifecycle = self.services.mcp_lifecycle
        from mcp.client.stdio import stdio_client as original_stdio_client

        @asynccontextmanager
        async def custom_stdio_client(server_params, errlog=sys.stderr):
            # Map agent name to the correct server name/service name
            if agent_instance.name == "business_discovery_agent":
                server_name = "local_search_server"
                mcp_service = ServiceName.LOCAL_SEARCH_MCP
            elif agent_instance.name == "website_analysis_agent":
                server_name = "web_analyzer_server"
                mcp_service = ServiceName.WEB_ANALYZER_MCP
            else:
                server_name = agent_instance.name
                mcp_service = ServiceName.LOCAL_SEARCH_MCP

            cb = self._fp.cb_registry.get_breaker(mcp_service)
            if not cb.allow_request():
                if session_id:
                    self._mc.record_service_request(session_id, mcp_service, "reject")
                raise GrowthScoutRuntimeError(
                    error_code=RuntimeErrorCode.CIRCUIT_BREAKER_OPEN,
                    message=f"Circuit breaker is OPEN for MCP service: {mcp_service.value}",
                    service=mcp_service,
                    retryable=False,
                    correlation_id=request.correlation_id,
                )

            if not mcp_lifecycle:
                try:
                    async with original_stdio_client(server_params, errlog) as streams:
                        if session_id:
                            self._mc.record_service_request(session_id, mcp_service, "success")
                        cb.record_success()
                        yield streams
                except Exception as e:
                    if session_id:
                        self._mc.record_service_request(session_id, mcp_service, "failure")
                    cb.record_failure()
                    raise e
                return

            cmd = server_params.command
            args = server_params.args
            env = server_params.env or {}

            try:
                # Acquire reference from manager with a timeout
                await asyncio.wait_for(
                    mcp_lifecycle.acquire(server_name, cmd, args, env),
                    timeout=self._config.mcp_timeout_seconds
                )
                instance = mcp_lifecycle._servers[server_name]
                process = instance.process

                import anyio
                from mcp.client.stdio import TextReceiveStream, SessionMessage, types as mcp_types
                
                read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
                write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

                async def stdout_reader():
                    assert process.stdout, "Opened process is missing stdout"
                    try:
                        async with read_stream_writer:
                            buffer = ""
                            async for chunk in TextReceiveStream(
                                process.stdout,
                                encoding=server_params.encoding,
                                errors=server_params.encoding_error_handler,
                            ):
                                lines = (buffer + chunk).split("\n")
                                buffer = lines.pop()
                                for line in lines:
                                    try:
                                        message = mcp_types.JSONRPCMessage.model_validate_json(line)
                                    except Exception as exc:
                                        await read_stream_writer.send(exc)
                                        continue
                                    session_message = SessionMessage(message)
                                    await read_stream_writer.send(session_message)
                    except anyio.ClosedResourceError:
                        pass

                async def stdin_writer():
                    assert process.stdin, "Opened process is missing stdin"
                    try:
                        async with write_stream_reader:
                            async for session_message in write_stream_reader:
                                json_data = session_message.message.model_dump_json(by_alias=True, exclude_none=True)
                                await process.stdin.send(
                                    (json_data + "\n").encode(
                                        encoding=server_params.encoding,
                                        errors=server_params.encoding_error_handler,
                                    )
                                )
                    except anyio.ClosedResourceError:
                        pass

                async with anyio.create_task_group() as tg:
                    tg.start_soon(stdout_reader)
                    tg.start_soon(stdin_writer)
                    try:
                        cb.record_success()
                        if session_id:
                            self._mc.record_service_request(session_id, mcp_service, "success")
                        yield read_stream, write_stream
                    finally:
                        await read_stream.aclose()
                        await write_stream.aclose()
                        await read_stream_writer.aclose()
                        await write_stream_reader.aclose()
                        await mcp_lifecycle.release(server_name)
            except Exception as e:
                cb.record_failure()
                if session_id:
                    self._mc.record_service_request(session_id, mcp_service, "failure")
                raise e

        # Run with timeout and stdio_client patch
        with patch("google.adk.tools.mcp_tool.mcp_session_manager.stdio_client", custom_stdio_client):
            raw_res = await asyncio.wait_for(_run(), timeout=request.timeout)

        # Harden output parsing with balanced-brace JSON extraction
        return self._parse_agent_output(
            raw_output=raw_res,
            output_schema=output_schema,
            worker_name=request.worker_name,
            session_id=session_id or "default",
        )

    def _parse_agent_output(
        self,
        raw_output: Any,
        output_schema: Type[BaseModel],
        worker_name: str,
        session_id: str,
    ) -> BaseModel:
        trace = self.get_trace(session_id)
        wf_id = trace.workflow_id if trace else "unknown_wf"

        # 1. Structured ADK output
        if isinstance(raw_output, output_schema):
            self._add_trace_entry(session_id, wf_id, "output_parsing", {
                "worker_name": worker_name,
                "path": "structured",
                "success": True
            })
            return raw_output

        if isinstance(raw_output, dict):
            try:
                validated = output_schema.model_validate(raw_output)
                self._add_trace_entry(session_id, wf_id, "output_parsing", {
                    "worker_name": worker_name,
                    "path": "structured",
                    "success": True
                })
                return validated
            except Exception as e:
                self._add_trace_entry(session_id, wf_id, "output_parsing", {
                    "worker_name": worker_name,
                    "path": "failed",
                    "success": False,
                    "error": str(e)
                })
                raise ValueError(f"Pydantic validation failed for dictionary output: {str(e)}")

        # 2. JSON extraction fallback
        if isinstance(raw_output, str):
            json_str = extract_balanced_json(raw_output)
            if json_str:
                import json
                try:
                    data = json.loads(json_str)
                    validated = output_schema.model_validate(data)
                    self._add_trace_entry(session_id, wf_id, "output_parsing", {
                        "worker_name": worker_name,
                        "path": "json_fallback",
                        "success": True
                    })
                    return validated
                except Exception as e:
                    self._add_trace_entry(session_id, wf_id, "output_parsing", {
                        "worker_name": worker_name,
                        "path": "failed",
                        "success": False,
                        "error": str(e)
                    })
                    raise ValueError(f"JSON validation failed for extracted JSON: {str(e)}")
            else:
                self._add_trace_entry(session_id, wf_id, "output_parsing", {
                    "worker_name": worker_name,
                    "path": "failed",
                    "success": False,
                    "error": "No balanced JSON object found in agent string output."
                })
                raise ValueError("No balanced JSON object found in agent string output.")

        # 3. Failed validation
        self._add_trace_entry(session_id, wf_id, "output_parsing", {
            "worker_name": worker_name,
            "path": "failed",
            "success": False,
            "error": f"Unsupported raw output type: {type(raw_output)}"
        })
        raise ValueError(f"Unsupported raw output type: {type(raw_output)}")

    def _apply_transition_plan(
        self,
        context: WorkflowContext,
        plan: TransitionPlan,
        acting_agent: str,
        reason: str,
    ) -> WorkflowContext:
        for hook in self.before_transition_hooks:
            try:
                hook(context, plan)
            except Exception:
                pass

        now = self.services.clock.now_utc()
        target_state = plan.target_state
        target_node = WORKFLOW_TOPOLOGY[target_state]

        # ── 1. Validate proposed transition ────────────────────────────────────
        result = self._tc.validate(
            context=context,
            requested_next=target_state,
            acting_agent=acting_agent,
            reason=reason,
        )
        if not result.is_valid:
            self._aw.append(result.audit_entry)
            raise InvalidTransitionError(
                f"Transition denied [{result.validation_status.value}]: "
                f"{result.denial_reason}"
            )

        # ── 2. Apply plan context updates to candidate new_context ─────────────
        new_context = context.with_state(new_state=target_state, timestamp=now)
        if plan.context_patch:
            new_context = new_context.model_copy(update=plan.context_patch)

        # ── 3. Validate evidence requirements on candidate context ─────────────
        if target_node.required_evidence:
            ev_result = self._ev.validate(
                context=new_context,
                required_evidence=target_node.required_evidence,
            )
            if not ev_result.passed:
                ev_entry = AuditTrailEntry(
                    entry_id=f"evt_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    event_type=AuditEventType.VALIDATION_FAILED,
                    workflow_state=context.current_state,
                    acting_agent=acting_agent,
                    timestamp=now,
                    input_references=[],
                    output_references=[],
                    transition_reason=f"Evidence validation failed: {ev_result.missing_details}",
                    partition_summary=context.partition_summary,
                    recovery_id=getattr(context, "recovery_id", None) or getattr(new_context, "recovery_id", None),
                )
                self._aw.append(ev_entry)
                raise EvidenceValidationError(
                    f"Evidence requirements not met for state {target_state.value}. "
                    f"Missing: {ev_result.failed_requirements}"
                )

        # ── 4. Memory Governance validation ─────────────────────────────────────
        # Check permissions for target state's write domains
        for domain in target_node.memory_write_domains:
            if domain == "business_profiles":
                agent_to_check = "business_discovery_agent"
            elif domain == "audit_history":
                agent_to_check = "website_analysis_agent"
            elif domain in ("opportunity_history", "competitor_snapshots"):
                agent_to_check = "opportunity_agent"
            elif domain == "growth_reports":
                agent_to_check = "growth_intelligence_agent"
            else:
                agent_to_check = acting_agent

            policy = "append_only_immutable" if domain == "audit_history" else "overwrite"
            decision = self._mg.evaluate_write(agent_to_check, domain, keys=[], policy=policy)
            if not decision.allowed:
                # If memory validation fails, transition directly to FAILED (Rule 11)
                self._add_trace_entry(context.session_id, context.workflow_id, "memory_violation", {"domain": domain})
                self._ep.publish(MemoryWritten(
                    event_id=f"ev_{uuid.uuid4().hex[:8]}",
                    session_id=context.session_id,
                    workflow_id=context.workflow_id,
                    occurred_at=now,
                    correlation_id=context.execution_metadata.correlation_id,
                    domain=domain,
                    keys=[],
                    operation="write",
                    writing_agent=acting_agent
                ))
                # Transition directly to FAILED
                failed_plan = TransitionPlan(
                    target_state=WorkflowState.FAILED,
                    context_patch={},
                    create_checkpoint=True,
                    publish_events=True,
                    metadata={"reason": f"memory_ownership_violation: write denied for {domain}"}
                )
                return self._apply_transition_plan(context, failed_plan, acting_agent, "Memory governance violation")

        # ── 5. Apply plan atomically ───────────────────────────────────────────
        prev_state = context.current_state
        recovery_id = getattr(context, "recovery_id", None) or getattr(new_context, "recovery_id", None)

        # ── 5. Record transitions, checkpoint, events ─────────────────────────
        # Exit entry
        exit_entry = AuditTrailEntry(
            entry_id=f"evt_{uuid.uuid4().hex[:8]}",
            session_id=context.session_id,
            workflow_id=context.workflow_id,
            event_type=AuditEventType.STATE_EXITED,
            workflow_state=prev_state,
            acting_agent=acting_agent,
            timestamp=now,
            input_references=[],
            output_references=[target_state.value],
            transition_reason=reason,
            partition_summary=context.partition_summary,
            recovery_id=recovery_id,
        )
        self._aw.append(exit_entry)
        
        audit_entry = result.audit_entry
        if recovery_id and audit_entry:
            audit_entry = audit_entry.model_copy(update={"recovery_id": recovery_id})
        self._aw.append(audit_entry)

        # Trace
        self._add_trace_entry(new_context.session_id, new_context.workflow_id, "transition", {
            "from_state": prev_state.value,
            "to_state": target_state.value,
            "reason": reason
        })
        self._mc.record_transition(new_context.session_id, prev_state.value, target_state.value)

        # Checkpoint
        if plan.create_checkpoint:
            if not hasattr(self, "_budgets"):
                self._budgets = {}
            if new_context.session_id not in self._budgets and new_context.budget is not None:
                self._budgets[new_context.session_id] = new_context.budget

            if not hasattr(self, "_worker_timelines"):
                self._worker_timelines = {}
            if new_context.session_id not in self._worker_timelines and new_context.worker_timeline:
                from .interfaces.worker_invocation import WorkerExecutionResult
                self._worker_timelines[new_context.session_id] = [
                    WorkerExecutionResult.model_validate(res) if isinstance(res, dict) else res
                    for res in new_context.worker_timeline
                ]

            budget = self._get_or_create_budget(new_context.session_id)
            timeline = [res.model_dump(mode="json") if hasattr(res, "model_dump") else res for res in self._worker_timelines.get(new_context.session_id, [])]
            checkpoint_context = new_context.model_copy(update={
                "budget": budget,
                "worker_timeline": timeline,
                "metrics": self._mc.get_metrics(new_context.session_id),
                "service_metrics": self._mc.get_service_metrics(new_context.session_id),
            })
            checkpoint_version = self._ci.next_version(new_context.session_id)
            checkpoint = CheckpointInterface.build(
                context=checkpoint_context,
                audit_trail=self._aw.read_trail(new_context.session_id),
                checkpoint_version=checkpoint_version
            )
            self._ci.save(checkpoint)
            self._mc.record_checkpoint_save(new_context.session_id)
            self._add_trace_entry(new_context.session_id, new_context.workflow_id, "checkpoint_created", {"version": checkpoint_version})

            if plan.publish_events:
                self._ep.publish(CheckpointSaved(
                    event_id=f"ev_{uuid.uuid4().hex[:8]}",
                    session_id=new_context.session_id,
                    workflow_id=new_context.workflow_id,
                    occurred_at=now,
                    correlation_id=new_context.execution_metadata.correlation_id,
                    checkpoint_version=checkpoint_version,
                    context_state=target_state
                ))

        # Event
        if plan.publish_events:
            self._ep.publish(TransitionExecuted(
                event_id=f"ev_{uuid.uuid4().hex[:8]}",
                session_id=new_context.session_id,
                workflow_id=new_context.workflow_id,
                occurred_at=now,
                correlation_id=new_context.execution_metadata.correlation_id,
                from_state=prev_state,
                to_state=target_state,
                reason=reason
            ))

        for hook in self.after_transition_hooks:
            try:
                hook(context, new_context)
            except Exception:
                pass

        return new_context


def extract_balanced_json(text: str) -> Optional[str]:
    """
    Locates the first '{' and finds its matching balanced '}'.
    Ignores braces inside double quotes, handling escaped quotes.
    Returns the JSON string or None if not found or unbalanced.
    """
    start_idx = text.find('{')
    if start_idx == -1:
        return None
        
    brace_count = 0
    in_quote = False
    escaped = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if escaped:
            escaped = False
            continue
            
        if char == '\\':
            escaped = True
            continue
            
        if char == '"':
            in_quote = not in_quote
            continue
            
        if not in_quote:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return text[start_idx:i+1]
                    
    return None
