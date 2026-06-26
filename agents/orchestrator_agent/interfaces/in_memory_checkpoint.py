# agents/orchestrator_agent/interfaces/in_memory_checkpoint.py
from collections import defaultdict
from typing import Dict, List
from .checkpoint import CheckpointInterface, WorkflowCheckpoint
from ..exceptions import CheckpointNotFoundError, CheckpointConflictError

class InMemoryCheckpointInterface(CheckpointInterface):
    """
    In-memory store for WorkflowCheckpoint persistence.
    """
    def __init__(self) -> None:
        super().__init__()
        # session_id → {checkpoint_version → WorkflowCheckpoint}
        self._store: Dict[str, Dict[int, WorkflowCheckpoint]] = defaultdict(dict)

    def save(self, checkpoint: WorkflowCheckpoint) -> str:
        session_id = checkpoint.session_id
        version = checkpoint.checkpoint_version

        existing_versions = self._store.get(session_id, {})
        if existing_versions:
            max_existing = max(existing_versions.keys())
            if version <= max_existing:
                raise CheckpointConflictError(
                    f"checkpoint_version={version} conflicts with existing "
                    f"max version={max_existing} for session '{session_id}'. "
                    "Stale write rejected."
                )

        self._store[session_id][version] = checkpoint
        return f"{session_id}:v{version}"

    def load(self, session_id: str) -> WorkflowCheckpoint:
        versions = self._store.get(session_id, {})
        if not versions:
            raise CheckpointNotFoundError(
                f"No checkpoint found for session '{session_id}'."
            )
        latest_version = max(versions.keys())
        return versions[latest_version]

    def load_version(self, session_id: str, checkpoint_version: int) -> WorkflowCheckpoint:
        versions = self._store.get(session_id, {})
        if checkpoint_version not in versions:
            raise CheckpointNotFoundError(
                f"Checkpoint v{checkpoint_version} not found for session '{session_id}'."
            )
        return versions[checkpoint_version]

    def list_versions(self, session_id: str) -> List[int]:
        return sorted(self._store.get(session_id, {}).keys())

    def next_version(self, session_id: str) -> int:
        versions = self._store.get(session_id, {})
        return max(versions.keys()) + 1 if versions else 1
