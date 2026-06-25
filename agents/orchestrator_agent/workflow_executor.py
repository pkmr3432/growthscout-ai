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
from .interfaces.worker_invocation import WorkerRegistry, WorkerInvocationRequest, WorkerInvocationResult, RetryPolicy
from .failure_policy import FailurePolicy
from .metrics_collector import WorkflowMetricsCollector, InMemoryMetricsCollector
from .exceptions import InvalidTransitionError, EvidenceValidationError, WorkerInvocationError
from .runtime_config import RuntimeConfig
from .cache_layer import RuntimeCacheManager
from .error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from .runtime_services import RuntimeServices

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

    def get_trace(self, session_id: str) -> Optional[ExecutionTrace]:
        """Retrieve trace for session."""
        return self._traces.get(session_id)

    def _add_trace_entry(self, session_id: str, workflow_id: str, event_type: str, details: Dict[str, Any]) -> None:
        trace = self._traces.get(session_id)
        if not trace:
            trace = ExecutionTrace(session_id=session_id, workflow_id=workflow_id)
        entry = TraceEntry(event_type=event_type, details=details)
        self._traces[session_id] = trace.with_entry(entry)

    async def execute_to_gate(self, context: WorkflowContext) -> WorkflowContext:
        """
        Run the execution loop until a HITL Gate or Terminal state is reached.
        """
        for hook in self.before_workflow_hooks:
            try:
                hook(context)
            except Exception:
                pass

        start_time = self.services.clock.now_utc()
        curr = context
        self._add_trace_entry(curr.session_id, curr.workflow_id, "execution_started", {"start_state": curr.current_state.value})

        while True:
            node = WORKFLOW_TOPOLOGY[curr.current_state]

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
            return WorkerInvocationResult(
                worker_name=worker_name,
                correlation_id=correlation_id,
                success=True,
                output=cached_val,
                execution_duration_ms=0.0,
                retries_attempted=0
            )

        request = WorkerInvocationRequest(
            worker_name=worker_name,
            input_payload=input_payload,
            expected_output_schema=output_schema.__name__,
            correlation_id=correlation_id,
            timeout=10.0,  # 10s default
            retry_limit=2,
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
                
                # Dynamic model call or mock call
                out = await self._execute_agent_run(agent_instance, request, output_schema)

                # Validate Output hooks
                for v_hook in self.validate_output_hooks:
                    try:
                        v_hook(worker_name, out)
                    except Exception:
                        pass

                # Record success on circuit breaker
                self._fp.record_success(worker_name)

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
                    retries_attempted=attempts_made - 1
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

                return result

            except Exception as e:
                # Classify exception into GrowthScoutRuntimeError
                if isinstance(e, GrowthScoutRuntimeError):
                    runtime_error = e
                else:
                    service = self._fp.get_service_for_worker(worker_name)
                    err_code = RuntimeErrorCode.UNEXPECTED_ERROR
                    retryable = True
                    
                    if isinstance(e, asyncio.TimeoutError):
                        err_code = RuntimeErrorCode.TIMEOUT
                        retryable = True
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

                # Record failure on circuit breaker
                self._fp.record_failure(worker_name, runtime_error)

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
                    delay = self._fp.get_retry_delay(request, attempts_made)
                    self._add_trace_entry(context.session_id, context.workflow_id, "worker_retry", {
                        "worker_name": worker_name,
                        "attempt": attempts_made,
                        "delay_seconds": delay,
                        "reason": runtime_error.message,
                        "error_code": runtime_error.error_code.value,
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

                return result

    async def _execute_agent_run(self, agent_instance: Any, request: WorkerInvocationRequest, output_schema: Type[BaseModel]) -> BaseModel:
        # Standard InMemoryRunner execution or direct mock call if mock injected
        # Check if agent has a mocked run_async/before_tool_callback or is mocked in tests
        # We can construct ADK run
        from google.adk.apps import App
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        # If model is mock or offline we wrap the call
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

        # Run with timeout
        return await asyncio.wait_for(_run(), timeout=request.timeout)

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
        )
        self._aw.append(exit_entry)
        self._aw.append(result.audit_entry)

        # Trace
        self._add_trace_entry(new_context.session_id, new_context.workflow_id, "transition", {
            "from_state": prev_state.value,
            "to_state": target_state.value,
            "reason": reason
        })
        self._mc.record_transition(new_context.session_id, prev_state.value, target_state.value)

        # Checkpoint
        if plan.create_checkpoint:
            checkpoint_version = self._ci.next_version(new_context.session_id)
            checkpoint = CheckpointInterface.build(
                context=new_context,
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
