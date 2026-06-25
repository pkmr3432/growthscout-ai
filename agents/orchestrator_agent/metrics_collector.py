# agents/orchestrator_agent/metrics_collector.py
"""
WorkflowMetricsCollector and InMemoryMetricsCollector for Phase 4B and 5.1.

Ownership: orchestrator_agent
"""
from __future__ import annotations

from typing import Dict, Protocol, runtime_checkable, Optional
from pydantic import BaseModel, Field

class MetricsSnapshot(BaseModel):
    transition_counts: Dict[str, int] = Field(default_factory=dict)
    worker_executions: Dict[str, int] = Field(default_factory=dict)
    retries: Dict[str, int] = Field(default_factory=dict)
    failures: Dict[str, int] = Field(default_factory=dict)
    latencies_ms: Dict[str, float] = Field(default_factory=dict)
    workflow_duration_ms: float = 0.0
    checkpoint_restores: int = 0
    checkpoint_saves: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_evictions: int = 0
    cache_expired: int = 0

    model_config = {
        "frozen": True
    }


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

    def record_checkpoint_save(self, session_id: str) -> None:
        ...

    def record_latency(self, session_id: str, component: str, latency_ms: float) -> None:
        ...

    def record_duration(self, session_id: str, duration_ms: float) -> None:
        ...

    def record_completion(self, session_id: str, success: bool) -> None:
        ...

    def get_metrics(self, session_id: str) -> Dict[str, int]:
        ...

    def snapshot(self, session_id: str, cache_stats: Optional[Dict[str, int]] = None) -> MetricsSnapshot:
        ...


class InMemoryMetricsCollector:
    """In-memory collector tracking execution numbers per session."""

    def __init__(self) -> None:
        # session_id -> metric_name -> count
        self._metrics: Dict[str, Dict[str, int]] = {}
        # session_id -> component -> total_latency
        self._latencies: Dict[str, Dict[str, float]] = {}
        self._durations: Dict[str, float] = {}
        self._checkpoint_saves: Dict[str, int] = {}

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

    def record_checkpoint_save(self, session_id: str) -> None:
        self._checkpoint_saves[session_id] = self._checkpoint_saves.get(session_id, 0) + 1

    def record_latency(self, session_id: str, component: str, latency_ms: float) -> None:
        if session_id not in self._latencies:
            self._latencies[session_id] = {}
        self._latencies[session_id][component] = latency_ms

    def record_duration(self, session_id: str, duration_ms: float) -> None:
        self._durations[session_id] = duration_ms

    def record_completion(self, session_id: str, success: bool) -> None:
        s = self._ensure_session(session_id)
        if success:
            s["completions_total"] += 1
        else:
            s["failures_total"] += 1

    def get_metrics(self, session_id: str) -> Dict[str, int]:
        return dict(self._ensure_session(session_id))

    def snapshot(self, session_id: str, cache_stats: Optional[Dict[str, int]] = None) -> MetricsSnapshot:
        s = self._ensure_session(session_id)
        c_stats = cache_stats or {}
        return MetricsSnapshot(
            transition_counts={
                "transitions_total": s["transitions_total"],
                "completions_total": s["completions_total"],
                "failures_total": s["failures_total"],
            },
            worker_executions={
                "worker_executions_total": s["worker_executions_total"],
            },
            retries={
                "worker_retries_total": s["worker_retries_total"],
            },
            failures={
                "worker_failures_total": s["worker_failures_total"],
            },
            latencies_ms=dict(self._latencies.get(session_id, {})),
            workflow_duration_ms=self._durations.get(session_id, 0.0),
            checkpoint_restores=s["checkpoint_restores_total"],
            checkpoint_saves=self._checkpoint_saves.get(session_id, 0),
            cache_hits=c_stats.get("hits", 0),
            cache_misses=c_stats.get("misses", 0),
            cache_evictions=c_stats.get("evictions", 0),
            cache_expired=c_stats.get("expired_entries", 0),
        )

