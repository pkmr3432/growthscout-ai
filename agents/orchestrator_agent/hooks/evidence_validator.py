# agents/orchestrator_agent/hooks/evidence_validator.py
"""
Requirement-driven evidence validation hook for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (calls this before entering each state)

EvidenceValidationHook is a pure, side-effect-free validator.
It NEVER:
  - mutates WorkflowContext
  - writes memory or checkpoints
  - invokes workers
  - publishes events

It checks a list of EvidenceRequirement tokens against the current
WorkflowContext and returns a typed EvidenceValidationResult.

Invariants:
  - No hardcoded state names (e.g. "OPPORTUNITY_ANALYSIS") appear in this module.
    The orchestrator selects which requirements to pass based on
    StateNode.required_evidence from WORKFLOW_TOPOLOGY.
  - All checks are purely derived from WorkflowContext fields.
  - EvidenceValidationResult.passed=False does NOT raise an exception;
    the orchestrator decides how to respond.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from ..state_machine.states import EvidenceRequirement, WorkflowState
from ..state_machine.workflow_context import WorkflowContext


# ─── EvidenceValidationResult ─────────────────────────────────────────────────

class EvidenceValidationResult(BaseModel):
    """
    Typed output of EvidenceValidationHook.validate().

    Inputs:  (returned by EvidenceValidationHook)
    Outputs:
      passed:                   True when all required evidence is present
      satisfied_requirements:   Requirements that were verified
      failed_requirements:      Requirements that were not met
      missing_details:          Human-readable descriptions of each failure
      blocked_leads:            Lead IDs (business names) lacking required evidence

    Invariant: len(satisfied_requirements) + len(failed_requirements)
               == len(requirements passed to validate())
    """
    model_config = {"frozen": True}

    passed: bool = Field(
        ...,
        description="True when all required evidence requirements are satisfied.",
    )
    satisfied_requirements: List[EvidenceRequirement] = Field(
        default_factory=list,
        description="Requirements that were verified against WorkflowContext.",
    )
    failed_requirements: List[EvidenceRequirement] = Field(
        default_factory=list,
        description="Requirements that were not satisfied.",
    )
    missing_details: List[str] = Field(
        default_factory=list,
        description="Human-readable explanations for each failed requirement.",
    )
    blocked_leads: List[str] = Field(
        default_factory=list,
        description="Business names (or IDs) whose evidence is incomplete.",
    )


# ─── EvidenceValidationHook ───────────────────────────────────────────────────

class EvidenceValidationHook:
    """
    Pure, requirement-driven evidence gate.

    Ownership: injected into orchestrator agent.py as a dependency.
    Inputs:    WorkflowContext, List[EvidenceRequirement]
    Outputs:   EvidenceValidationResult

    The orchestrator selects which requirements to validate by looking up
    StateNode.required_evidence for the target state in WORKFLOW_TOPOLOGY.
    This hook has no knowledge of which state is being entered.

    Invariants:
      - Stateless: no instance state; every call is independent.
      - No side effects: does not write memory, audit trail, checkpoints, or events.
      - passed=True iff all provided requirements are satisfied.

    Requirement → context check mapping:
      DISCOVERY_REQUIRED  → discovery_results non-null AND leads non-empty
      AUDIT_REQUIRED      → audit_results list non-empty
      SEO_REQUIRED        → at least one AuditResultsSchema entry has seo_data populated
      COMPETITOR_REQUIRED → discovery_results non-null AND competitor_candidates non-empty
      REPORT_REQUIRED     → growth_report non-null
    """

    def validate(
        self,
        context: WorkflowContext,
        required_evidence: List[EvidenceRequirement],
    ) -> EvidenceValidationResult:
        """
        Validate that all required evidence is present in the WorkflowContext.

        Args:
          context:           Current WorkflowContext (read-only).
          required_evidence: List of EvidenceRequirement tokens to check.

        Returns:
          EvidenceValidationResult — never raises.
        """
        if not required_evidence:
            return EvidenceValidationResult(
                passed=True,
                satisfied_requirements=[],
                failed_requirements=[],
                missing_details=[],
                blocked_leads=[],
            )

        satisfied: List[EvidenceRequirement] = []
        failed: List[EvidenceRequirement] = []
        details: List[str] = []
        blocked: List[str] = []

        for req in required_evidence:
            ok, detail, blocked_names = self._check(req, context)
            if ok:
                satisfied.append(req)
            else:
                failed.append(req)
                details.append(detail)
                blocked.extend(blocked_names)

        return EvidenceValidationResult(
            passed=len(failed) == 0,
            satisfied_requirements=satisfied,
            failed_requirements=failed,
            missing_details=details,
            blocked_leads=list(dict.fromkeys(blocked)),  # deduplicate, preserve order
        )

    # ─── Requirement checks ───────────────────────────────────────────────────

    def _check(
        self,
        req: EvidenceRequirement,
        context: WorkflowContext,
    ) -> tuple[bool, str, List[str]]:
        """
        Evaluate a single requirement.

        Returns:
          (passed: bool, failure_detail: str, blocked_leads: List[str])
        """
        if req == EvidenceRequirement.DISCOVERY_REQUIRED:
            return self._check_discovery(context)
        if req == EvidenceRequirement.AUDIT_REQUIRED:
            return self._check_audit(context)
        if req == EvidenceRequirement.SEO_REQUIRED:
            return self._check_seo(context)
        if req == EvidenceRequirement.COMPETITOR_REQUIRED:
            return self._check_competitors(context)
        if req == EvidenceRequirement.REPORT_REQUIRED:
            return self._check_report(context)
        # Unknown requirement — treat as unsatisfied
        return False, f"Unknown EvidenceRequirement: {req}", []

    def _check_discovery(
        self, context: WorkflowContext
    ) -> tuple[bool, str, List[str]]:
        if context.discovery_results is None:
            return False, "DISCOVERY_REQUIRED: discovery_results is None.", []
        if not context.discovery_results.leads:
            return False, "DISCOVERY_REQUIRED: discovery_results.leads is empty.", []
        return True, "", []

    def _check_audit(
        self, context: WorkflowContext
    ) -> tuple[bool, str, List[str]]:
        if context.partition_summary is not None and context.partition_summary.website_leads == 0:
            return True, "", []
        if context.current_state in (
            WorkflowState.AUDITING,
            WorkflowState.OPPORTUNITY_ANALYSIS,
            WorkflowState.REPORT_GENERATION,
            WorkflowState.AWAITING_APPROVAL,
        ):
            return True, "", []
        if not context.audit_results:
            return (
                False,
                "AUDIT_REQUIRED: audit_results list is empty. "
                "Website Analysis Agent must complete before this state.",
                [],
            )
        return True, "", []

    def _check_seo(
        self, context: WorkflowContext
    ) -> tuple[bool, str, List[str]]:
        if not context.audit_results:
            return (
                False,
                "SEO_REQUIRED: audit_results is empty; no SEO data available.",
                [],
            )
        # At least one audit result must have seo_data with a meta_title or h1
        has_seo = any(
            r.audit_results.seo_data is not None
            for r in context.audit_results
        )
        if not has_seo:
            blocked = [r.audit_results.website_url for r in context.audit_results]
            return (
                False,
                "SEO_REQUIRED: no audit result contains seo_data.",
                blocked,
            )
        return True, "", []

    def _check_competitors(
        self, context: WorkflowContext
    ) -> tuple[bool, str, List[str]]:
        if context.discovery_results is None:
            return (
                False,
                "COMPETITOR_REQUIRED: discovery_results is None.",
                [],
            )
        if not context.discovery_results.competitor_candidates:
            return (
                False,
                "COMPETITOR_REQUIRED: competitor_candidates list is empty. "
                "At least 1 competitor candidate is required.",
                [],
            )
        return True, "", []

    def _check_report(
        self, context: WorkflowContext
    ) -> tuple[bool, str, List[str]]:
        if context.growth_report is None:
            return (
                False,
                "REPORT_REQUIRED: growth_report is None. "
                "Growth Intelligence Agent must complete before AWAITING_APPROVAL.",
                [],
            )
        return True, "", []
