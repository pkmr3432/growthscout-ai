# agents/orchestrator_agent/interfaces/resumability.py
"""
Workflow resumability controller for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole authority for workflow recovery)

ResumabilityController determines whether a halted workflow can be resumed
and from which state, using CheckpointInterface for state restoration.

Invariants:
  - Terminal states cannot be resumed; ResumeResult(resumed=False) is returned.
  - Schema version mismatches return resumed=False (not an exception) unless
    the mismatch is irrecoverable (e.g. unknown schema), in which case
    WorkflowResumeError is raised.
  - ResumabilityController never mutates WorkflowContext, writes memory,
    or publishes events.
  - Only the orchestrator (agent.py) acts on a successful ResumeResult.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .checkpoint import CheckpointInterface, WorkflowCheckpoint, CURRENT_SCHEMA_VERSION, WORKFLOW_VERSION
from ..state_machine.states import WorkflowState, TERMINAL_STATES
from ..exceptions import CheckpointNotFoundError, WorkflowResumeError


# ─── ResumeResult ─────────────────────────────────────────────────────────────

class ResumeResult(BaseModel):
    """
    Typed output of ResumabilityController.resume().

    Inputs:  (returned by ResumabilityController)
    Outputs:
      resumed:          True when the workflow can be resumed
      from_state:       State to resume from (None when resumed=False)
      checkpoint:       Checkpoint used for restoration (None when resumed=False)
      denial_reason:    Human-readable reason for non-resumable cases

    denial_reason values:
      "no_checkpoint_found"      — no checkpoint exists for the session
      "terminal_state"           — current state is terminal; workflow is complete
      "schema_version_mismatch"  — checkpoint schema is incompatible with current version
      "workflow_version_mismatch" — workflow routing version is incompatible
      "checkpoint_version_invalid" — checkpoint version must be >= 1
    """
    model_config = {"frozen": True}

    resumed: bool = Field(..., description="True when the workflow can be resumed.")
    from_state: Optional[WorkflowState] = Field(
        None,
        description="State to resume execution from.",
    )
    checkpoint: Optional[WorkflowCheckpoint] = Field(
        None,
        description="Checkpoint used for state restoration.",
    )
    denial_reason: Optional[str] = Field(
        None,
        description="Reason for non-resumable result.",
    )


# ─── ResumabilityController ───────────────────────────────────────────────────

class ResumabilityController:
    """
    Determines whether a halted workflow session can be resumed.

    Ownership: injected into orchestrator agent.py as a dependency.
    Inputs:    session_id string, CheckpointInterface instance
    Outputs:   ResumeResult

    Invariants:
      - Never mutates WorkflowContext.
      - Returns ResumeResult(resumed=False) for terminal states and missing checkpoints.
      - Raises WorkflowResumeError only for genuinely irrecoverable conditions
        (e.g. checkpoint schema version from a completely unknown format).
    """

    def __init__(self, checkpoint_interface: CheckpointInterface) -> None:
        """
        Args:
          checkpoint_interface: The CheckpointInterface instance to use for state loading.
        """
        self._checkpoints = checkpoint_interface

    def can_resume(self, session_id: str) -> ResumeResult:
        """
        Check if a session can be resumed without committing to resumption.

        Same logic as resume() but does not signal any side effects.
        """
        return self._evaluate(session_id)

    def resume(self, session_id: str) -> ResumeResult:
        """
        Attempt to resume a halted workflow from its latest checkpoint.

        Args:
          session_id: The session to resume.

        Returns:
          ResumeResult with resumed=True and from_state/checkpoint populated
          if resumption is possible; resumed=False with denial_reason otherwise.

        Raises:
          WorkflowResumeError: Only for irrecoverable schema incompatibilities
          that cannot be expressed as a simple denial_reason.
        """
        return self._evaluate(session_id)

    # ─── Private ──────────────────────────────────────────────────────────────

    def _evaluate(self, session_id: str) -> ResumeResult:
        """Core evaluation logic shared by can_resume() and resume()."""

        # 1. Attempt to load latest checkpoint
        try:
            checkpoint = self._checkpoints.load(session_id)
        except CheckpointNotFoundError:
            return ResumeResult(
                resumed=False,
                from_state=None,
                checkpoint=None,
                denial_reason="no_checkpoint_found",
            )

        # 2. Validate schema version compatibility
        schema_ok = self._is_schema_compatible(checkpoint.schema_version)
        if not schema_ok:
            return ResumeResult(
                resumed=False,
                from_state=None,
                checkpoint=None,
                denial_reason="schema_version_mismatch",
            )

        # 2.5 Validate workflow version and checkpoint version
        if checkpoint.workflow_version != WORKFLOW_VERSION:
            return ResumeResult(
                resumed=False,
                from_state=None,
                checkpoint=None,
                denial_reason="workflow_version_mismatch",
            )

        if checkpoint.checkpoint_version < 1:
            return ResumeResult(
                resumed=False,
                from_state=None,
                checkpoint=None,
                denial_reason="checkpoint_version_invalid",
            )

        # 3. Check if the checkpointed state is terminal
        restored_state = checkpoint.context_snapshot.current_state
        if restored_state in TERMINAL_STATES:
            return ResumeResult(
                resumed=False,
                from_state=restored_state,
                checkpoint=checkpoint,
                denial_reason="terminal_state",
            )

        # 4. Resumption is possible
        return ResumeResult(
            resumed=True,
            from_state=restored_state,
            checkpoint=checkpoint,
            denial_reason=None,
        )

    @staticmethod
    def _is_schema_compatible(checkpoint_schema_version: str) -> bool:
        """
        Check if the checkpoint's schema_version is compatible with the current system.

        Phase 4A: only CURRENT_SCHEMA_VERSION ("4.0") is accepted.
        Future phases may implement a migration table here.
        """
        return checkpoint_schema_version == CURRENT_SCHEMA_VERSION
