# agents/orchestrator_agent/circuit_breaker.py
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from .service_names import ServiceName

class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    def __init__(
        self,
        name: ServiceName,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        success_threshold: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_state_change = datetime.now(timezone.utc)
        self.opened_at: Optional[datetime] = None

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)

    def allow_request(self) -> bool:
        self._check_cooldown()
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def _check_cooldown(self) -> None:
        if self.state == CircuitState.OPEN and self.opened_at:
            elapsed = (datetime.now(timezone.utc) - self.opened_at).total_seconds()
            if elapsed >= self.cooldown_seconds:
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        self.state = new_state
        self.last_state_change = datetime.now(timezone.utc)
        if new_state == CircuitState.OPEN:
            self.opened_at = self.last_state_change
            self.success_count = 0
        elif new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
            self.opened_at = None
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0

class CircuitBreakerRegistry:
    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
        success_threshold: int = 1,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.success_threshold = success_threshold
        self._breakers: Dict[ServiceName, CircuitBreaker] = {}

    def get_breaker(self, service_name: ServiceName) -> CircuitBreaker:
        if service_name not in self._breakers:
            self._breakers[service_name] = CircuitBreaker(
                name=service_name,
                failure_threshold=self.failure_threshold,
                cooldown_seconds=self.cooldown_seconds,
                success_threshold=self.success_threshold,
            )
        return self._breakers[service_name]
