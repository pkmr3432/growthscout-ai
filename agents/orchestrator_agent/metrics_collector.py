# agents/orchestrator_agent/metrics_collector.py
"""
WorkflowMetricsCollector and InMemoryMetricsCollector for Phase 4B.

Ownership: orchestrator_agent
"""
from __future__ import annotations

from typing import Dict, Protocol, runtime_checkable

@runtime_checkable
class WorkflowMetricsCollector(Protocol):
    """Protocol for recording workflow run metrics."""

    def record_transition(self, session_id: str, from_state: str, to_state: str) -> None:
        ...

    def record_worker_execution(self, session_id: str, worker_name: str) -> None:
        ...

    def record_worker_retry(self, session_id: str, worker_name: str) -> None:
        ...

    def record_worker_failure(self, session_id: str, worker_name: str) -> None:
        ...

    def record_checkpoint_restore(self, session_id: str) -> None:
        ...

    def record_completion(self, session_id: str, success: bool) -> None:
        ...

    def get_metrics(self, session_id: str) -> Dict[str, int]:
        ...


class InMemoryMetricsCollector:
    """In-memory collector tracking execution numbers per session."""

    def __init__(self) -> None:
        # session_id -> metric_name -> count
        self._metrics: Dict[str, Dict[str, int]] = {}

    def _ensure_session(self, session_id: str) -> Dict[str, int]:
        if session_id not in self._metrics:
            self._metrics[session_id] = {
                "transitions_total": 0,
                "worker_executions_total": 0,
                "worker_retries_total": 0,
                "worker_failures_total": 0,
                "checkpoint_restores_total": 0,
                "completions_total": 0,
                "failures_total": 0,
            }
        return self._metrics[session_id]

    def record_transition(self, session_id: str, from_state: str, to_state: str) -> None:
        s = self._ensure_session(session_id)
        s["transitions_total"] += 1

    def record_worker_execution(self, session_id: str, worker_name: str) -> None:
        s = self._ensure_session(session_id)
        s["worker_executions_total"] += 1

    def record_worker_retry(self, session_id: str, worker_name: str) -> None:
        s = self._ensure_session(session_id)
        s["worker_retries_total"] += 1

    def record_worker_failure(self, session_id: str, worker_name: str) -> None:
        s = self._ensure_session(session_id)
        s["worker_failures_total"] += 1

    def record_checkpoint_restore(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["checkpoint_restores_total"] += 1

    def record_completion(self, session_id: str, success: bool) -> None:
        s = self._ensure_session(session_id)
        if success:
            s["completions_total"] += 1
        else:
            s["failures_total"] += 1

    def get_metrics(self, session_id: str) -> Dict[str, int]:
        return dict(self._ensure_session(session_id))
