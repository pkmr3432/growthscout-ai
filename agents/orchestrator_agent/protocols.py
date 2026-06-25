# agents/orchestrator_agent/protocols.py
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from pydantic import BaseModel

from .state_machine.states import WorkflowState
from .service_names import ServiceName

@runtime_checkable
class ClockProtocol(Protocol):
    def now_utc(self) -> datetime:
        ...

class SystemClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

class FrozenClock:
    def __init__(self, time_val: datetime) -> None:
        self._time = time_val

    def set_time(self, time_val: datetime) -> None:
        self._time = time_val

    def now_utc(self) -> datetime:
        return self._time

@runtime_checkable
class CacheProtocol(Protocol):
    def get(self, key: str) -> Optional[Any]:
        ...
    def set(self, key: str, value: Any) -> None:
        ...
    def invalidate(self, key: str) -> None:
        ...
    def clear(self) -> None:
        ...
    @property
    def hits(self) -> int:
        ...
    @property
    def misses(self) -> int:
        ...
    @property
    def evictions(self) -> int:
        ...
    @property
    def expired_entries(self) -> int:
        ...

@runtime_checkable
class MetricsCollectorProtocol(Protocol):
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
    def snapshot(self, session_id: str, cache_stats: Optional[Dict[str, int]] = None) -> Any:
        ...

@runtime_checkable
class CircuitBreakerProtocol(Protocol):
    def record_success(self) -> None:
        ...
    def record_failure(self) -> None:
        ...
    def allow_request(self) -> bool:
        ...
    @property
    def state(self) -> Any:
        ...

@runtime_checkable
class HealthCheckProtocol(Protocol):
    async def run_checks(self) -> List[Any]:
        ...
