# agents/orchestrator_agent/interfaces/checkpoint.py
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from ..state_machine.workflow_context import WorkflowContext
from ..hooks.audit_trail import AuditTrailEntry
from ..exceptions import CheckpointNotFoundError, CheckpointVersionConflictError
from ..runtime_config import RuntimeConfig

CURRENT_SCHEMA_VERSION = "4.0"
WORKFLOW_VERSION = "1.3.0"

class WorkflowCheckpoint(BaseModel):
    """
    Versioned, portable snapshot of workflow runtime state.
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
    revision: int = Field(
        default=1,
        description="Monotonic write revision number.",
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

class CheckpointInterface(ABC):
    """
    Pure abstract save/load contract for WorkflowCheckpoint persistence.
    """
    def __new__(cls, *args, **kwargs):
        if cls is CheckpointInterface:
            from .in_memory_checkpoint import InMemoryCheckpointInterface
            instance = object.__new__(InMemoryCheckpointInterface)
            instance.__init__(*args, **kwargs)
            return instance
        return object.__new__(cls)

    @abstractmethod
    def save(self, checkpoint: WorkflowCheckpoint) -> str:
        pass

    @abstractmethod
    def load(self, session_id: str) -> WorkflowCheckpoint:
        pass

    @abstractmethod
    def load_version(self, session_id: str, checkpoint_version: int) -> WorkflowCheckpoint:
        pass

    @abstractmethod
    def list_versions(self, session_id: str) -> List[int]:
        pass

    @abstractmethod
    def next_version(self, session_id: str) -> int:
        pass

    @staticmethod
    def build(
        context: WorkflowContext,
        audit_trail: List[AuditTrailEntry],
        checkpoint_version: int,
    ) -> WorkflowCheckpoint:
        return WorkflowCheckpoint(
            schema_version=CURRENT_SCHEMA_VERSION,
            workflow_version=WORKFLOW_VERSION,
            checkpoint_version=checkpoint_version,
            revision=checkpoint_version,
            session_id=context.session_id,
            workflow_id=context.workflow_id,
            context_snapshot=context,
            audit_trail_snapshot=list(audit_trail),
            saved_at=datetime.now(timezone.utc),
        )

class CheckpointProviderFactory:
    @staticmethod
    def create(
        config: RuntimeConfig,
        cb_registry: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
    ) -> CheckpointInterface:
        backend = config.checkpoint_backend.lower() if config.checkpoint_backend else "in_memory"
        if backend == "firestore":
            try:
                from .firestore_checkpoint import FirestoreCheckpointInterface
                return FirestoreCheckpointInterface(config, cb_registry=cb_registry, metrics_collector=metrics_collector)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Firestore checkpoint initialization failed: {e}. Falling back to InMemoryCheckpointInterface.")
                from .in_memory_checkpoint import InMemoryCheckpointInterface
                return InMemoryCheckpointInterface()
        else:
            from .in_memory_checkpoint import InMemoryCheckpointInterface
            return InMemoryCheckpointInterface()

