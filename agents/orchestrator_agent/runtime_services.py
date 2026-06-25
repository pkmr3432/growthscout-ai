# agents/orchestrator_agent/runtime_services.py
from dataclasses import dataclass
from .runtime_config import RuntimeConfig
from .protocols import ClockProtocol, CacheProtocol, MetricsCollectorProtocol, HealthCheckProtocol
from .circuit_breaker import CircuitBreakerRegistry
from .failure_policy import FailurePolicy
from .interfaces.worker_invocation import WorkerRegistry
from .hooks.audit_trail import AuditTrailWriter
from .interfaces.checkpoint import CheckpointInterface
from .interfaces.events import EventPublisher

@dataclass(frozen=True)
class RuntimeServices:
    config: RuntimeConfig
    cache_manager: CacheProtocol
    metrics_collector: MetricsCollectorProtocol
    cb_registry: CircuitBreakerRegistry
    failure_policy: FailurePolicy
    clock: ClockProtocol
    event_publisher: EventPublisher
    audit_writer: AuditTrailWriter
    checkpoint_interface: CheckpointInterface
    worker_registry: WorkerRegistry
    preflight_validator: HealthCheckProtocol
