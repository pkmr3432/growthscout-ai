# agents/orchestrator_agent/metrics_collector.py
"""
WorkflowMetricsCollector and InMemoryMetricsCollector for Phase 4B, 5.1, and 5.2.5.

Ownership: orchestrator_agent
"""
from __future__ import annotations

from typing import Dict, Protocol, runtime_checkable, Optional, Any
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
    
    # Validation metrics
    validation_runs_total: int = 0
    validation_failures_total: int = 0
    schema_failures_total: int = 0
    business_failures_total: int = 0
    normalized_outputs_total: int = 0
    warnings_total: int = 0

    # Resilience metrics
    retry_attempts: int = 0
    timeout_count: int = 0
    circuit_breaker_open_total: int = 0
    circuit_breaker_half_open_total: int = 0
    circuit_breaker_recovered_total: int = 0
    resumed_workflows: int = 0
    failed_resumptions: int = 0
    recovery_duration_ms: float = 0.0

    # Per-service breaker health counters
    # maps: service_name -> {"successful_requests": int, "failed_requests": int, "rejected_requests": int}
    service_metrics: Dict[str, Dict[str, int]] = Field(default_factory=dict)

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

    def record_validation(
        self,
        session_id: str,
        worker_name: str,
        validator_name: str,
        duration_ms: float,
        success: bool,
        failure_type: Optional[str] = None,
        warnings_count: int = 0,
        normalized: bool = False,
    ) -> None:
        ...

    # Resilience methods
    def record_retry_attempt(self, session_id: str) -> None:
        ...

    def record_timeout(self, session_id: str) -> None:
        ...

    def record_circuit_breaker_open(self, session_id: str) -> None:
        ...

    def record_circuit_breaker_half_open(self, session_id: str) -> None:
        ...

    def record_circuit_breaker_recovered(self, session_id: str) -> None:
        ...

    def record_resumed_workflow(self, session_id: str) -> None:
        ...

    def record_failed_resumption(self, session_id: str) -> None:
        ...

    def record_recovery_duration(self, session_id: str, duration_ms: float) -> None:
        ...

    def record_service_request(self, session_id: str, service: str, outcome: str) -> None:
        """outcome is one of 'success', 'failure', 'reject'"""
        ...

    def get_metrics(self, session_id: str) -> Dict[str, int]:
        ...

    def restore_metrics(self, session_id: str, metrics: Dict[str, int], service_metrics: Optional[Dict[str, Dict[str, int]]] = None) -> None:
        ...

    def get_service_metrics(self, session_id: str) -> Dict[str, Dict[str, int]]:
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
        # session_id -> service_name -> outcome_name -> count
        self._service_metrics: Dict[str, Dict[str, Dict[str, int]]] = {}
        # session_id -> recovery_duration_ms
        self._recovery_durations: Dict[str, float] = {}

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
                "validation_runs_total": 0,
                "validation_failures_total": 0,
                "schema_failures_total": 0,
                "business_failures_total": 0,
                "normalized_outputs_total": 0,
                "warnings_total": 0,
                # Resilience
                "retry_attempts": 0,
                "timeout_count": 0,
                "circuit_breaker_open_total": 0,
                "circuit_breaker_half_open_total": 0,
                "circuit_breaker_recovered_total": 0,
                "resumed_workflows": 0,
                "failed_resumptions": 0,
            }
        return self._metrics[session_id]

    def _ensure_service_metrics(self, session_id: str, service: str) -> Dict[str, int]:
        if session_id not in self._service_metrics:
            self._service_metrics[session_id] = {}
        if service not in self._service_metrics[session_id]:
            self._service_metrics[session_id][service] = {
                "successful_requests": 0,
                "failed_requests": 0,
                "rejected_requests": 0,
            }
        return self._service_metrics[session_id][service]

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

    def record_validation(
        self,
        session_id: str,
        worker_name: str,
        validator_name: str,
        duration_ms: float,
        success: bool,
        failure_type: Optional[str] = None,
        warnings_count: int = 0,
        normalized: bool = False,
    ) -> None:
        s = self._ensure_session(session_id)
        s["validation_runs_total"] += 1
        if not success:
            s["validation_failures_total"] += 1
            if failure_type == "schema":
                s["schema_failures_total"] += 1
            elif failure_type == "business":
                s["business_failures_total"] += 1
        if normalized:
            s["normalized_outputs_total"] += 1
        s["warnings_total"] += warnings_count

        if session_id not in self._latencies:
            self._latencies[session_id] = {}
        self._latencies[session_id][f"validation_duration_ms:{worker_name}"] = duration_ms

    # Resilience implementations
    def record_retry_attempt(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["retry_attempts"] += 1

    def record_timeout(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["timeout_count"] += 1

    def record_circuit_breaker_open(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["circuit_breaker_open_total"] += 1

    def record_circuit_breaker_half_open(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["circuit_breaker_half_open_total"] += 1

    def record_circuit_breaker_recovered(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["circuit_breaker_recovered_total"] += 1

    def record_resumed_workflow(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["resumed_workflows"] += 1

    def record_failed_resumption(self, session_id: str) -> None:
        s = self._ensure_session(session_id)
        s["failed_resumptions"] += 1

    def record_recovery_duration(self, session_id: str, duration_ms: float) -> None:
        self._recovery_durations[session_id] = duration_ms

    def record_service_request(self, session_id: str, service: str, outcome: str) -> None:
        sm = self._ensure_service_metrics(session_id, service)
        if outcome == "success":
            sm["successful_requests"] += 1
        elif outcome == "failure":
            sm["failed_requests"] += 1
        elif outcome == "reject":
            sm["rejected_requests"] += 1

    def get_metrics(self, session_id: str) -> Dict[str, int]:
        return dict(self._ensure_session(session_id))

    def restore_metrics(self, session_id: str, metrics: Dict[str, int], service_metrics: Optional[Dict[str, Dict[str, int]]] = None) -> None:
        self._metrics[session_id] = dict(metrics)
        if service_metrics:
            self._service_metrics[session_id] = {
                service: dict(outcomes) for service, outcomes in service_metrics.items()
            }

    def get_service_metrics(self, session_id: str) -> Dict[str, Dict[str, int]]:
        if session_id in self._service_metrics:
            return {s: dict(o) for s, o in self._service_metrics[session_id].items()}
        return {}

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
            validation_runs_total=s.get("validation_runs_total", 0),
            validation_failures_total=s.get("validation_failures_total", 0),
            schema_failures_total=s.get("schema_failures_total", 0),
            business_failures_total=s.get("business_failures_total", 0),
            normalized_outputs_total=s.get("normalized_outputs_total", 0),
            warnings_total=s.get("warnings_total", 0),
            # Resilience
            retry_attempts=s.get("retry_attempts", 0),
            timeout_count=s.get("timeout_count", 0),
            circuit_breaker_open_total=s.get("circuit_breaker_open_total", 0),
            circuit_breaker_half_open_total=s.get("circuit_breaker_half_open_total", 0),
            circuit_breaker_recovered_total=s.get("circuit_breaker_recovered_total", 0),
            resumed_workflows=s.get("resumed_workflows", 0),
            failed_resumptions=s.get("failed_resumptions", 0),
            recovery_duration_ms=self._recovery_durations.get(session_id, 0.0),
            service_metrics=self.get_service_metrics(session_id),
        )
