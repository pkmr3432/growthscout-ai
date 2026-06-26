# agents/orchestrator_agent/interfaces/firestore_checkpoint.py
import os
import logging
from typing import List, Optional, Any
from .checkpoint import CheckpointInterface, WorkflowCheckpoint
from ..exceptions import CheckpointNotFoundError, CheckpointConflictError
from ..runtime_config import RuntimeConfig
from ..service_names import ServiceName
from ..error_codes import RuntimeErrorCode, GrowthScoutRuntimeError

logger = logging.getLogger(__name__)

class FirestoreCheckpointInterface(CheckpointInterface):
    """
    Firestore-backed store for WorkflowCheckpoint persistence.
    """
    def __init__(
        self,
        config: RuntimeConfig,
        cb_registry: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
    ) -> None:
        super().__init__()
        from google.cloud import firestore
        from google.auth.exceptions import DefaultCredentialsError

        self.config = config
        self.cb_registry = cb_registry
        self.metrics_collector = metrics_collector
        self.collection_name = os.environ.get("FIRESTORE_CHECKPOINT_COLLECTION", "checkpoints")
        try:
            self.db = firestore.Client()
        except (DefaultCredentialsError, Exception) as e:
            logger.warning(f"Firestore Client authentication failed: {e}")
            raise RuntimeError(f"Firestore authentication failed: {e}") from e

    def _check_cb_and_record_outcome(self, session_id: str, operation_callable: Any, *args, **kwargs) -> Any:
        """Helper to run a firestore operation protected by the firestore circuit breaker and timeout."""
        if self.cb_registry:
            cb = self.cb_registry.get_breaker(ServiceName.FIRESTORE)
            if not cb.allow_request():
                if self.metrics_collector:
                    self.metrics_collector.record_service_request(session_id, ServiceName.FIRESTORE, "reject")
                raise GrowthScoutRuntimeError(
                    error_code=RuntimeErrorCode.CIRCUIT_BREAKER_OPEN,
                    message="Circuit breaker is OPEN for Firestore service.",
                    service=ServiceName.FIRESTORE,
                    retryable=False,
                )

        try:
            # Inject timeout
            kwargs["timeout"] = self.config.firestore_timeout_seconds
            res = operation_callable(*args, **kwargs)
            if self.cb_registry:
                cb.record_success()
            if self.metrics_collector:
                self.metrics_collector.record_service_request(session_id, ServiceName.FIRESTORE, "success")
            return res
        except Exception as e:
            if self.cb_registry:
                cb.record_failure()
            if self.metrics_collector:
                self.metrics_collector.record_service_request(session_id, ServiceName.FIRESTORE, "failure")
            raise e

    def save(self, checkpoint: WorkflowCheckpoint) -> str:
        from google.cloud import firestore
        session_id = checkpoint.session_id
        version = checkpoint.checkpoint_version

        # Monotonic and optimistic concurrency checks using wrapper
        query = self.db.collection(self.collection_name)\
            .where("session_id", "==", session_id)\
            .order_by("checkpoint_version", direction=firestore.Query.DESCENDING)\
            .limit(1)

        docs = self._check_cb_and_record_outcome(session_id, lambda **kwargs: list(query.stream(**kwargs)))
        if docs:
            latest_version = docs[0].to_dict().get("checkpoint_version", 0)
            if version <= latest_version:
                raise CheckpointConflictError(
                    f"checkpoint_version={version} conflicts with existing "
                    f"max version={latest_version} for session '{session_id}'. "
                    "Stale write rejected."
                )

        doc_ref = self.db.collection(self.collection_name).document(f"{session_id}_v{version}")
        doc_data = checkpoint.model_dump(mode="json")
        self._check_cb_and_record_outcome(session_id, doc_ref.set, doc_data)
        return f"{session_id}:v{version}"

    def load(self, session_id: str) -> WorkflowCheckpoint:
        from google.cloud import firestore
        query = self.db.collection(self.collection_name)\
            .where("session_id", "==", session_id)\
            .order_by("checkpoint_version", direction=firestore.Query.DESCENDING)\
            .limit(1)

        docs = self._check_cb_and_record_outcome(session_id, lambda **kwargs: list(query.stream(**kwargs)))
        if not docs:
            raise CheckpointNotFoundError(
                f"No checkpoint found for session '{session_id}'."
            )
        return WorkflowCheckpoint.model_validate(docs[0].to_dict())

    def load_version(self, session_id: str, checkpoint_version: int) -> WorkflowCheckpoint:
        doc_ref = self.db.collection(self.collection_name).document(f"{session_id}_v{checkpoint_version}")
        doc = self._check_cb_and_record_outcome(session_id, doc_ref.get)
        if not doc.exists:
            raise CheckpointNotFoundError(
                f"Checkpoint v{checkpoint_version} not found for session '{session_id}'."
            )
        return WorkflowCheckpoint.model_validate(doc.to_dict())

    def list_versions(self, session_id: str) -> List[int]:
        query = self.db.collection(self.collection_name)\
            .where("session_id", "==", session_id)

        docs = self._check_cb_and_record_outcome(session_id, lambda **kwargs: list(query.stream(**kwargs)))
        versions = []
        for doc in docs:
            v = doc.to_dict().get("checkpoint_version")
            if v is not None:
                versions.append(int(v))
        return sorted(versions)

    def next_version(self, session_id: str) -> int:
        versions = self.list_versions(session_id)
        return max(versions) + 1 if versions else 1
