# agents/orchestrator_agent/state_machine/workflow_context.py
"""
Canonical runtime state model for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole authority for creating/replacing instances)

WorkflowContext is the single typed carrier passed to every orchestration
component. It is treated as immutable — components return new results;
only the orchestrator agent creates updated instances.

Invariants:
  - Never mutate a WorkflowContext in-place; always construct a new one.
  - Worker output schemas from agents.shared.schemas are embedded directly
    (no duplication of field definitions).
  - session_id must match pattern: sess_[a-f0-9]{8}
  - workflow_id must match pattern: wf_[a-f0-9]{8}
  - revision_count must be in range [0, 5] per workflow_routing.yaml governance.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from .states import WorkflowState

# Worker output schemas — imported for embedding in WorkflowContext.
# These are the frozen contracts from agents/shared/schemas.py.
from agents.shared.schemas import (
    DiscoveryLeadsSchema,
    AuditResultsSchema,
    OpportunityAnalysisSchema,
    GrowthReportsSchema,
)

# ─── Sub-models ───────────────────────────────────────────────────────────────

_SESSION_ID_PATTERN = re.compile(r"^sess_[a-f0-9]{8}$")
_WORKFLOW_ID_PATTERN = re.compile(r"^wf_[a-f0-9]{8}$")
_MAX_REVISION_COUNT = 5


class EvidenceReference(BaseModel):
    """
    Traceability record linking a tool execution to a captured artifact.

    Inputs:  tool_name, execution_id, domain, artifact_key, captured_at
    Outputs: (pure data)

    Invariant: Every scored opportunity must trace back to an EvidenceReference
               from audit_history or competitor_snapshots per memory governance.
    """
    model_config = {"frozen": True}

    tool_name: str = Field(..., description="Name of the MCP tool that produced this evidence.")
    execution_id: str = Field(..., description="Unique ID of the specific tool invocation.")
    domain: str = Field(..., description="Memory domain where the artifact was stored.")
    artifact_key: str = Field(..., description="Key within the domain referencing the artifact.")
    captured_at: datetime = Field(..., description="UTC timestamp when the evidence was captured.")


class PartitionSummary(BaseModel):
    """
    Counts from the LEAD_PARTITIONING state — required for audit trail entries.

    Invariant: total_leads == website_leads + no_website_leads when integrity_valid=True.
    """
    model_config = {"frozen": True}

    total_leads: int = Field(..., ge=0, description="Total discovered leads before partitioning.")
    website_leads: int = Field(..., ge=0, description="Leads with a resolvable website URL.")
    no_website_leads: int = Field(..., ge=0, description="Leads without a website URL.")
    integrity_valid: bool = Field(
        ...,
        description="True when total_leads == website_leads + no_website_leads.",
    )

    @model_validator(mode="after")
    def _check_integrity(self) -> PartitionSummary:
        expected = self.website_leads + self.no_website_leads
        if self.integrity_valid and expected != self.total_leads:
            raise ValueError(
                f"integrity_valid=True but total_leads={self.total_leads} != "
                f"website_leads({self.website_leads}) + no_website_leads({self.no_website_leads})"
            )
        return self


class ExecutionMetadata(BaseModel):
    """
    Runtime provenance metadata for this workflow run.

    Inputs:  orchestrator_version, adk_version, correlation_id
    Outputs: (pure data)
    """
    model_config = {"frozen": True}

    orchestrator_version: str = Field(
        default="4.0",
        description="Phase 4A schema version of the orchestrator.",
    )
    adk_version: str = Field(
        default="unknown",
        description="google-adk package version resolved at runtime.",
    )
    correlation_id: str = Field(
        ...,
        description="Unique ID tying this run to external request logs.",
    )


class WorkflowMetadata(BaseModel):
    """
    User-supplied search parameters for this workflow run.

    Invariant: niche and location are required; max_leads defaults to 5.
    """
    model_config = {"frozen": True}

    niche: str = Field(..., description="Business vertical category (e.g. 'HVAC repair').")
    location: str = Field(..., description="Target geographic city/state (e.g. 'Austin, TX').")
    max_leads: int = Field(default=5, ge=1, le=50, description="Max leads to discover.")


class WorkflowTimestamps(BaseModel):
    """
    UTC timestamps for lifecycle tracking across the workflow run.

    Invariant: updated_at >= created_at
    """
    model_config = {"frozen": True}

    created_at: datetime = Field(..., description="When this workflow session was created.")
    updated_at: datetime = Field(..., description="Last time the WorkflowContext was replaced.")
    state_entered_at: datetime = Field(
        ...,
        description="When current_state was entered.",
    )
    estimated_deadline: Optional[datetime] = Field(
        None,
        description="Optional wall-clock cutoff for the full workflow run.",
    )

    @model_validator(mode="after")
    def _check_chronology(self) -> WorkflowTimestamps:
        if self.updated_at < self.created_at:
            raise ValueError(
                f"updated_at ({self.updated_at}) must be >= created_at ({self.created_at})"
            )
        return self


# ─── WorkflowContext ──────────────────────────────────────────────────────────

class WorkflowContext(BaseModel):
    """
    Canonical, immutable runtime state for the GrowthScout AI workflow.

    Ownership: orchestrator_agent — only agent.py creates new instances.
    All validators, hooks, and interfaces take WorkflowContext as input
    and return typed results; they never modify this object.

    Inputs:
      session_id:          Unique session identifier (pattern: sess_[hex8])
      workflow_id:         Unique workflow run identifier (pattern: wf_[hex8])
      current_state:       Active WorkflowState
      discovery_results:   Output of business_discovery_agent (nullable)
      audit_results:       List of outputs from website_analysis_agent
      opportunity_results: Output of opportunity_agent (nullable)
      growth_report:       Output of growth_intelligence_agent (nullable)
      evidence_references: Traceability records linking tool runs to data
      revision_count:      HITL revision counter (0–5)
      partition_summary:   Populated after LEAD_PARTITIONING (nullable)
      execution_metadata:  Runtime provenance
      workflow_metadata:   User-supplied search parameters
      timestamps:          Lifecycle timestamps

    Invariants:
      - Treat as frozen; never mutate fields in-place.
      - revision_count in [0, 5] per workflow governance.
      - session_id matches sess_[a-f0-9]{8}
      - workflow_id matches wf_[a-f0-9]{8}
    """
    model_config = {"frozen": True}

    # ── Identity ──────────────────────────────────────────────────────────────
    session_id: str = Field(
        ...,
        description="Unique session identifier. Pattern: sess_[a-f0-9]{8}",
    )
    workflow_id: str = Field(
        ...,
        description="Unique workflow run identifier. Pattern: wf_[a-f0-9]{8}",
    )

    # ── Pipeline State ────────────────────────────────────────────────────────
    current_state: WorkflowState = Field(
        default=WorkflowState.IDLE,
        description="Active state in the workflow state machine.",
    )

    # ── Worker Outputs (progressive — populated as pipeline advances) ─────────
    discovery_results: Optional[DiscoveryLeadsSchema] = Field(
        None,
        description="Structured output from business_discovery_agent.",
    )
    audit_results: List[AuditResultsSchema] = Field(
        default_factory=list,
        description="Accumulated outputs from website_analysis_agent (one per domain).",
    )
    opportunity_results: Optional[OpportunityAnalysisSchema] = Field(
        None,
        description="Structured output from opportunity_agent.",
    )
    growth_report: Optional[GrowthReportsSchema] = Field(
        None,
        description="Structured output from growth_intelligence_agent.",
    )

    # ── Evidence Traceability ─────────────────────────────────────────────────
    evidence_references: List[EvidenceReference] = Field(
        default_factory=list,
        description="Tool execution trace records for audit compliance.",
    )

    # ── HITL Governance ───────────────────────────────────────────────────────
    revision_count: int = Field(
        default=0,
        ge=0,
        le=_MAX_REVISION_COUNT,
        description=f"HITL revision counter. Max {_MAX_REVISION_COUNT} per workflow governance.",
    )

    # ── Partitioning ──────────────────────────────────────────────────────────
    partition_summary: Optional[PartitionSummary] = Field(
        None,
        description="Lead partition counts, populated after LEAD_PARTITIONING state.",
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    execution_metadata: ExecutionMetadata = Field(
        ...,
        description="Runtime provenance: orchestrator version, ADK version, correlation ID.",
    )
    workflow_metadata: WorkflowMetadata = Field(
        ...,
        description="User-supplied search parameters: niche, location, max_leads.",
    )
    timestamps: WorkflowTimestamps = Field(
        ...,
        description="Lifecycle timestamps: created_at, updated_at, state_entered_at.",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, v: str) -> str:
        if not _SESSION_ID_PATTERN.match(v):
            raise ValueError(
                f"session_id '{v}' does not match required pattern sess_[a-f0-9]{{8}}"
            )
        return v

    @field_validator("workflow_id")
    @classmethod
    def _validate_workflow_id(cls, v: str) -> str:
        if not _WORKFLOW_ID_PATTERN.match(v):
            raise ValueError(
                f"workflow_id '{v}' does not match required pattern wf_[a-f0-9]{{8}}"
            )
        return v

    # ── Factory helpers ───────────────────────────────────────────────────────

    def with_state(self, new_state: WorkflowState, timestamp: datetime) -> "WorkflowContext":
        """
        Return a NEW WorkflowContext with current_state updated.

        The caller (orchestrator agent.py) is responsible for invoking this
        only after TransitionController.validate() returns is_valid=True.
        """
        return self.model_copy(
            update={
                "current_state": new_state,
                "timestamps": WorkflowTimestamps(
                    created_at=self.timestamps.created_at,
                    updated_at=timestamp,
                    state_entered_at=timestamp,
                    estimated_deadline=self.timestamps.estimated_deadline,
                ),
            }
        )

    def with_discovery(self, results: DiscoveryLeadsSchema, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with discovery_results populated."""
        return self.model_copy(
            update={
                "discovery_results": results,
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )

    def with_audit(self, result: AuditResultsSchema, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with one audit result appended."""
        return self.model_copy(
            update={
                "audit_results": [*self.audit_results, result],
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )

    def with_opportunity(self, results: OpportunityAnalysisSchema, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with opportunity_results populated."""
        return self.model_copy(
            update={
                "opportunity_results": results,
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )

    def with_growth_report(self, report: GrowthReportsSchema, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with growth_report populated."""
        return self.model_copy(
            update={
                "growth_report": report,
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )

    def with_partition(self, summary: PartitionSummary, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with partition_summary populated."""
        return self.model_copy(
            update={
                "partition_summary": summary,
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )

    def with_evidence(self, ref: EvidenceReference, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with one evidence reference appended."""
        return self.model_copy(
            update={
                "evidence_references": [*self.evidence_references, ref],
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )

    def with_incremented_revision(self, timestamp: datetime) -> "WorkflowContext":
        """Return a NEW WorkflowContext with revision_count incremented by 1."""
        return self.model_copy(
            update={
                "revision_count": self.revision_count + 1,
                "timestamps": self.timestamps.model_copy(update={"updated_at": timestamp}),
            }
        )
