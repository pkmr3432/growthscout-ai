# agents/orchestrator_agent/state_machine/states.py
"""
Workflow state topology for GrowthScout AI.

Ownership: orchestrator_agent (sole authority for state transitions)

This module is the single source of truth for:
  - WorkflowState enum — all 11 pipeline states
  - StateType enum — node execution topology types
  - EvidenceRequirement enum — typed gate tokens declared per-state
  - StateNode dataclass — per-state metadata (agent, evidence, memory domains)
  - WORKFLOW_TOPOLOGY — the complete state graph
  - TERMINAL_STATES / ACTIVE_STATES — convenience sets

Invariants:
  - No orchestration logic lives here; this is pure declarative data.
  - WORKFLOW_TOPOLOGY must cover every member of WorkflowState.
  - Terminal states have no allowed_transitions.
"""
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Enums ────────────────────────────────────────────────────────────────────

class WorkflowState(str, Enum):
    """
    All pipeline states for the GrowthScout AI workflow.

    Active states: IDLE → DISCOVERING → LEAD_PARTITIONING → AUDITING
                   → OPPORTUNITY_ANALYSIS → REPORT_GENERATION → AWAITING_APPROVAL

    Terminal states: COMPLETED, FAILED, CANCELLED, NO_LEADS_FOUND
    """
    # Active states
    IDLE = "IDLE"
    DISCOVERING = "DISCOVERING"
    LEAD_PARTITIONING = "LEAD_PARTITIONING"
    AUDITING = "AUDITING"
    OPPORTUNITY_ANALYSIS = "OPPORTUNITY_ANALYSIS"
    REPORT_GENERATION = "REPORT_GENERATION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"

    # Terminal states
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NO_LEADS_FOUND = "NO_LEADS_FOUND"


class StateType(str, Enum):
    """
    Node execution topology categories, per workflow_definitions.md.

    START       — pipeline entry point (IDLE)
    AGENT_NODE  — invokes a single named worker agent
    PARTITION_NODE — orchestrator-executed partitioning logic (no agent invoked)
    HITL_GATE   — suspends; waits for human callback (Phase 4B scope)
    END_NODE    — terminal; no further transitions permitted
    """
    START = "start"
    AGENT_NODE = "agent_node"
    PARTITION_NODE = "partition_node"
    HITL_GATE = "hitl_gate"
    END_NODE = "end_node"


class EvidenceRequirement(str, Enum):
    """
    Typed gate tokens checked by EvidenceValidationHook before state entry.

    Each WorkflowState declares which requirements must be satisfied.
    The hook validates them generically against WorkflowContext — no
    hardcoded state names appear inside EvidenceValidationHook.

    DISCOVERY_REQUIRED  — context.discovery_results non-null, leads non-empty
    AUDIT_REQUIRED      — context.audit_results list non-empty
    SEO_REQUIRED        — at least one audit entry has seo_data populated
    COMPETITOR_REQUIRED — context.discovery_results.competitor_candidates non-empty
    REPORT_REQUIRED     — context.growth_report non-null
    """
    DISCOVERY_REQUIRED = "DISCOVERY_REQUIRED"
    AUDIT_REQUIRED = "AUDIT_REQUIRED"
    SEO_REQUIRED = "SEO_REQUIRED"
    COMPETITOR_REQUIRED = "COMPETITOR_REQUIRED"
    REPORT_REQUIRED = "REPORT_REQUIRED"


# ─── StateNode ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StateNode:
    """
    Declarative metadata for a single workflow state.

    Inputs:  state — the WorkflowState this node describes
    Outputs: (pure data; no logic)

    Invariants:
      - Terminal states must have empty allowed_transitions.
      - owner_agent is None for partition_node, hitl_gate, and end_node types
        because the orchestrator owns those directly.
      - memory_write_domains and memory_read_domains reference the canonical
        domain names from memory_bank_config.yaml.
    """
    state: WorkflowState
    state_type: StateType
    owner_agent: Optional[str]
    default_next_state: Optional[WorkflowState] = None
    allowed_transitions: List[WorkflowState] = field(default_factory=list)
    required_evidence: List[EvidenceRequirement] = field(default_factory=list)
    memory_write_domains: List[str] = field(default_factory=list)
    memory_read_domains: List[str] = field(default_factory=list)


# ─── Workflow Topology ────────────────────────────────────────────────────────

WORKFLOW_TOPOLOGY: dict[WorkflowState, StateNode] = {

    WorkflowState.IDLE: StateNode(
        state=WorkflowState.IDLE,
        state_type=StateType.START,
        owner_agent=None,
        default_next_state=WorkflowState.DISCOVERING,
        allowed_transitions=[WorkflowState.DISCOVERING],
        required_evidence=[],
        memory_write_domains=["session_memory"],
        memory_read_domains=[],
    ),

    WorkflowState.DISCOVERING: StateNode(
        state=WorkflowState.DISCOVERING,
        state_type=StateType.AGENT_NODE,
        owner_agent="business_discovery_agent",
        allowed_transitions=[
            WorkflowState.LEAD_PARTITIONING,
            WorkflowState.NO_LEADS_FOUND,
            WorkflowState.FAILED,
        ],
        required_evidence=[],
        memory_write_domains=["session_memory", "business_profiles"],
        memory_read_domains=["session_memory"],
    ),

    WorkflowState.LEAD_PARTITIONING: StateNode(
        state=WorkflowState.LEAD_PARTITIONING,
        state_type=StateType.PARTITION_NODE,
        owner_agent=None,  # Executed directly by orchestrator
        default_next_state=WorkflowState.AUDITING,
        allowed_transitions=[
            WorkflowState.AUDITING,
            WorkflowState.OPPORTUNITY_ANALYSIS,
            WorkflowState.FAILED,
        ],
        required_evidence=[EvidenceRequirement.DISCOVERY_REQUIRED],
        memory_write_domains=["session_memory"],
        memory_read_domains=["session_memory"],
    ),

    WorkflowState.AUDITING: StateNode(
        state=WorkflowState.AUDITING,
        state_type=StateType.AGENT_NODE,
        owner_agent="website_analysis_agent",
        default_next_state=WorkflowState.OPPORTUNITY_ANALYSIS,
        allowed_transitions=[
            WorkflowState.OPPORTUNITY_ANALYSIS,
            WorkflowState.FAILED,
        ],
        required_evidence=[
            EvidenceRequirement.DISCOVERY_REQUIRED,
        ],
        memory_write_domains=["session_memory", "audit_history"],
        memory_read_domains=["session_memory", "business_profiles"],
    ),

    WorkflowState.OPPORTUNITY_ANALYSIS: StateNode(
        state=WorkflowState.OPPORTUNITY_ANALYSIS,
        state_type=StateType.AGENT_NODE,
        owner_agent="opportunity_agent",
        default_next_state=WorkflowState.REPORT_GENERATION,
        allowed_transitions=[
            WorkflowState.REPORT_GENERATION,
            WorkflowState.FAILED,
        ],
        required_evidence=[
            EvidenceRequirement.DISCOVERY_REQUIRED,
            EvidenceRequirement.COMPETITOR_REQUIRED,
            EvidenceRequirement.AUDIT_REQUIRED,
        ],
        memory_write_domains=["opportunity_history", "competitor_snapshots"],
        memory_read_domains=["audit_history", "business_profiles", "competitor_snapshots"],
    ),

    WorkflowState.REPORT_GENERATION: StateNode(
        state=WorkflowState.REPORT_GENERATION,
        state_type=StateType.AGENT_NODE,
        owner_agent="growth_intelligence_agent",
        default_next_state=WorkflowState.AWAITING_APPROVAL,
        allowed_transitions=[
            WorkflowState.AWAITING_APPROVAL,
            WorkflowState.FAILED,
        ],
        required_evidence=[
            EvidenceRequirement.DISCOVERY_REQUIRED,
            EvidenceRequirement.AUDIT_REQUIRED,
            EvidenceRequirement.COMPETITOR_REQUIRED,
        ],
        memory_write_domains=["growth_reports", "session_memory"],
        memory_read_domains=[
            "opportunity_history",
            "competitor_snapshots",
            "audit_history",
            "business_profiles",
            "human_notes",
        ],
    ),

    WorkflowState.AWAITING_APPROVAL: StateNode(
        state=WorkflowState.AWAITING_APPROVAL,
        state_type=StateType.HITL_GATE,
        owner_agent=None,  # Human user controls this gate
        allowed_transitions=[
            WorkflowState.COMPLETED,
            WorkflowState.REPORT_GENERATION,  # Rejection loop
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ],
        required_evidence=[EvidenceRequirement.REPORT_REQUIRED],
        memory_write_domains=["session_memory", "human_notes"],
        memory_read_domains=["growth_reports", "session_memory"],
    ),

    # ─── Terminal States ───────────────────────────────────────────────────────

    WorkflowState.COMPLETED: StateNode(
        state=WorkflowState.COMPLETED,
        state_type=StateType.END_NODE,
        owner_agent=None,
        allowed_transitions=[],  # Terminal
        required_evidence=[],
        memory_write_domains=[],
        memory_read_domains=[],
    ),

    WorkflowState.FAILED: StateNode(
        state=WorkflowState.FAILED,
        state_type=StateType.END_NODE,
        owner_agent=None,
        allowed_transitions=[],  # Terminal
        required_evidence=[],
        memory_write_domains=[],
        memory_read_domains=[],
    ),

    WorkflowState.CANCELLED: StateNode(
        state=WorkflowState.CANCELLED,
        state_type=StateType.END_NODE,
        owner_agent=None,
        allowed_transitions=[],  # Terminal
        required_evidence=[],
        memory_write_domains=[],
        memory_read_domains=[],
    ),

    WorkflowState.NO_LEADS_FOUND: StateNode(
        state=WorkflowState.NO_LEADS_FOUND,
        state_type=StateType.END_NODE,
        owner_agent=None,
        allowed_transitions=[],  # Terminal
        required_evidence=[],
        memory_write_domains=[],
        memory_read_domains=[],
    ),
}

# ─── Convenience Sets ─────────────────────────────────────────────────────────

TERMINAL_STATES: frozenset[WorkflowState] = frozenset({
    WorkflowState.COMPLETED,
    WorkflowState.FAILED,
    WorkflowState.CANCELLED,
    WorkflowState.NO_LEADS_FOUND,
})

ACTIVE_STATES: frozenset[WorkflowState] = frozenset(
    s for s in WorkflowState if s not in TERMINAL_STATES
)

# ─── Topology integrity check (runs at import time) ──────────────────────────

def _assert_topology_complete() -> None:
    """Verify that WORKFLOW_TOPOLOGY covers every WorkflowState member."""
    missing = [s for s in WorkflowState if s not in WORKFLOW_TOPOLOGY]
    if missing:
        raise AssertionError(
            f"WORKFLOW_TOPOLOGY is missing states: {[s.value for s in missing]}"
        )


_assert_topology_complete()
