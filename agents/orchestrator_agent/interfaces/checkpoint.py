# agents/orchestrator_agent/interfaces/checkpoint.py
"""
Versioned workflow checkpoint persistence for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole authority for saving/loading checkpoints)

This module defines:
  - WorkflowCheckpoint — versioned, portable snapshot of the full runtime state
  - CheckpointInterface — save/load abstraction with monotonic version enforcement

Invariants:
  - checkpoint_version is monotonically increasing; CheckpointVersionConflictError
    is raised if a non-monotonic version is saved.
  - schema_version enables future migration scripts to detect stale formats.
  - workflow_version must match workflow_routing.yaml version string.
  - Phase 4A: in-memory backing store keyed by (session_id, checkpoint_version).
    Phase 5 target: Firestore with the same public API.
  - CheckpointInterface never mutates WorkflowContext or publishes events.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ..state_machine.workflow_context import WorkflowContext
from ..hooks.audit_trail import AuditTrailEntry
from ..exceptions import CheckpointNotFoundError, CheckpointVersionConflictError

# Canonical schema version for Phase 4A checkpoints.
# Increment this when the WorkflowCheckpoint model gains breaking field changes.
CURRENT_SCHEMA_VERSION = "4.0"

# Must match workflow_routing.yaml → workflow.version
WORKFLOW_VERSION = "1.3.0"


# ─── WorkflowCheckpoint ───────────────────────────────────────────────────────

class WorkflowCheckpoint(BaseModel):
    """
    Versioned, portable snapshot of workflow runtime state.

    Inputs (provided by the orchestrator before calling CheckpointInterface.save()):
      schema_version:        Checkpoint format version (e.g. "4.0")
      workflow_version:      Workflow routing version (e.g. "1.3.0")
      checkpoint_version:    Monotonic counter for this session's checkpoints
      session_id:            Session identifier
      workflow_id:           Workflow run identifier
      context_snapshot:      Full WorkflowContext at time of save
      audit_trail_snapshot:  All audit entries recorded up to this point
      saved_at:              UTC timestamp of save

    Invariant: checkpoint_version must be >= 1 and strictly increasing per session.
    """
    model_config = {"frozen": True}

    schema_version: str = Field(
        default=CURRENT_SCHEMA_VERSION,
        description="Checkpoint schema version. Enables migration detection.",
    )
    workflow_version: str = Field(
        default=WORKFLOW_VERSION,
        description="Workflow routing version from workflow_routing.yaml.",
    )
    checkpoint_version: int = Field(
        ...,
        ge=1,
        description="Monotonic checkpoint counter for this session. Starts at 1.",
    )
    session_id: str = Field(..., description="Session this checkpoint belongs to.")
    workflow_id: str = Field(..., description="Workflow run this checkpoint belongs to.")
    context_snapshot: WorkflowContext = Field(
        ...,
        description="Full WorkflowContext captured at checkpoint save time.",
    )
    audit_trail_snapshot: List[AuditTrailEntry] = Field(
        default_factory=list,
        description="All audit entries up to the time of this checkpoint.",
    )
    saved_at: datetime = Field(
        ...,
        description="UTC timestamp when this checkpoint was saved.",
    )


# ─── CheckpointInterface ──────────────────────────────────────────────────────

class CheckpointInterface:
    """
    Save/load abstraction for WorkflowCheckpoint persistence.

    Ownership: injected into orchestrator agent.py as a dependency.
    Inputs:    WorkflowCheckpoint (save), session_id (load/list)
    Outputs:   WorkflowCheckpoint or version lists

    Invariants:
      - checkpoint_version must be strictly greater than the previous highest
        version for the session; otherwise CheckpointVersionConflictError is raised.
      - load() returns the checkpoint with the highest checkpoint_version.
      - Phase 4A: in-memory store; replace _store with Firestore adapter in Phase 5.
    """

    def __init__(self) -> None:
        # session_id → {checkpoint_version → WorkflowCheckpoint}
        self._store: Dict[str, Dict[int, WorkflowCheckpoint]] = defaultdict(dict)

    def save(self, checkpoint: WorkflowCheckpoint) -> str:
        """
        Persist a WorkflowCheckpoint.

        Args:
          checkpoint: The checkpoint to save.

        Returns:
          A checkpoint key string: "{session_id}:v{checkpoint_version}"

        Raises:
          CheckpointVersionConflictError: If checkpoint_version is not strictly
            greater than the highest existing version for the session.
        """
        session_id = checkpoint.session_id
        version = checkpoint.checkpoint_version

        existing_versions = self._store.get(session_id, {})
        if existing_versions:
            max_existing = max(existing_versions.keys())
            if version <= max_existing:
                raise CheckpointVersionConflictError(
                    f"checkpoint_version={version} conflicts with existing "
                    f"max version={max_existing} for session '{session_id}'. "
                    "checkpoint_version must be strictly increasing."
                )

        self._store[session_id][version] = checkpoint
        return f"{session_id}:v{version}"

    def load(self, session_id: str) -> WorkflowCheckpoint:
        """
        Load the latest checkpoint for a session.

        Args:
          session_id: The session to restore.

        Returns:
          The WorkflowCheckpoint with the highest checkpoint_version.

        Raises:
          CheckpointNotFoundError: If no checkpoint exists for the session.
        """
        versions = self._store.get(session_id, {})
        if not versions:
            raise CheckpointNotFoundError(
                f"No checkpoint found for session '{session_id}'."
            )
        latest_version = max(versions.keys())
        return versions[latest_version]

    def load_version(self, session_id: str, checkpoint_version: int) -> WorkflowCheckpoint:
        """
        Load a specific checkpoint version for a session.

        Raises:
          CheckpointNotFoundError: If the version does not exist.
        """
        versions = self._store.get(session_id, {})
        if checkpoint_version not in versions:
            raise CheckpointNotFoundError(
                f"Checkpoint v{checkpoint_version} not found for session '{session_id}'. "
                f"Available versions: {sorted(versions.keys())}"
            )
        return versions[checkpoint_version]

    def list_versions(self, session_id: str) -> List[int]:
        """
        Return sorted list of all checkpoint_version values for a session.

        Returns an empty list if no checkpoints exist.
        """
        return sorted(self._store.get(session_id, {}).keys())

    def next_version(self, session_id: str) -> int:
        """
        Return the next checkpoint_version to use for a session.

        Returns 1 if no checkpoints exist yet.
        """
        versions = self._store.get(session_id, {})
        return max(versions.keys()) + 1 if versions else 1

    @staticmethod
    def build(
        context: WorkflowContext,
        audit_trail: List[AuditTrailEntry],
        checkpoint_version: int,
    ) -> WorkflowCheckpoint:
        """
        Factory: construct a WorkflowCheckpoint from a context and audit trail.

        Args:
          context:           Current WorkflowContext to snapshot.
          audit_trail:       All audit entries up to this point.
          checkpoint_version: Monotonic version number for this checkpoint.

        Returns:
          A fully-populated WorkflowCheckpoint ready for save().
        """
        return WorkflowCheckpoint(
            schema_version=CURRENT_SCHEMA_VERSION,
            workflow_version=WORKFLOW_VERSION,
            checkpoint_version=checkpoint_version,
            session_id=context.session_id,
            workflow_id=context.workflow_id,
            context_snapshot=context,
            audit_trail_snapshot=list(audit_trail),
            saved_at=datetime.now(timezone.utc),
        )
