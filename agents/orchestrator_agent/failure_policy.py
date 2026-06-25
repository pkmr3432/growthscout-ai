# agents/orchestrator_agent/failure_policy.py
"""
FailurePolicy component for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent
Responsibility: Governs timeout handling, retry decisions, delays, circuit breakers, and failure state routing.
"""
from __future__ import annotations

import asyncio
from typing import Optional
from datetime import datetime, timezone

from .interfaces.worker_invocation import RetryPolicy, WorkerInvocationRequest
from .state_machine.states import WorkflowState
from .runtime_config import RuntimeConfig
from .circuit_breaker import CircuitBreakerRegistry
from .error_codes import RuntimeErrorCode, GrowthScoutRuntimeError
from .service_names import ServiceName

class FailurePolicy:
    """
    Failure policy governing retry, delay, recovery, circuit breakers, and failure routing.

    Invariants:
      - Side-effect free (pure logic for decisions).
      - Integrates stateful circuit breakers and config settings.
    """

    def __init__(
        self,
        config: Optional[RuntimeConfig] = None,
        cb_registry: Optional[CircuitBreakerRegistry] = None,
    ) -> None:
        self.config = config or RuntimeConfig.load_from_env()
        self.cb_registry = cb_registry or CircuitBreakerRegistry(
            failure_threshold=self.config.circuit_breaker_failure_threshold,
            cooldown_seconds=self.config.circuit_breaker_cooldown_seconds,
            success_threshold=self.config.circuit_breaker_success_threshold,
        )

    def get_service_for_worker(self, worker_name: str) -> ServiceName:
        if worker_name == "business_discovery_agent":
            return ServiceName.GOOGLE_MAPS
        elif worker_name == "website_analysis_agent":
            return ServiceName.WEBSITE_SCRAPER
        return ServiceName.GEMINI

    def check_circuit_breakers(self, worker_name: str, correlation_id: Optional[str] = None) -> None:
        """Check if breakers are open for either Gemini (all workers) or the specific service."""
        # All worker invocations use Gemini
        gemini_breaker = self.cb_registry.get_breaker(ServiceName.GEMINI)
        if not gemini_breaker.allow_request():
            raise GrowthScoutRuntimeError(
                error_code=RuntimeErrorCode.CIRCUIT_BREAKER_OPEN,
                message="Circuit breaker is OPEN for Gemini service.",
                service=ServiceName.GEMINI,
                retryable=False,
                correlation_id=correlation_id,
            )

        service = self.get_service_for_worker(worker_name)
        if service != ServiceName.GEMINI:
            service_breaker = self.cb_registry.get_breaker(service)
            if not service_breaker.allow_request():
                raise GrowthScoutRuntimeError(
                    error_code=RuntimeErrorCode.CIRCUIT_BREAKER_OPEN,
                    message=f"Circuit breaker is OPEN for {service.value} service.",
                    service=service,
                    retryable=False,
                    correlation_id=correlation_id,
                )

    def record_success(self, worker_name: str) -> None:
        self.cb_registry.get_breaker(ServiceName.GEMINI).record_success()
        service = self.get_service_for_worker(worker_name)
        if service != ServiceName.GEMINI:
            self.cb_registry.get_breaker(service).record_success()

    def record_failure(self, worker_name: str, error: Exception) -> None:
        service = self.get_service_for_worker(worker_name)
        if service != ServiceName.GEMINI:
            self.cb_registry.get_breaker(service).record_failure()
        else:
            self.cb_registry.get_breaker(ServiceName.GEMINI).record_failure()

    def should_retry(self, request: WorkerInvocationRequest, attempts_made: int, error: Exception) -> bool:
        """
        Determine if we should retry the invocation.
        """
        if isinstance(error, GrowthScoutRuntimeError):
            if not error.retryable:
                return False
            if error.error_code == RuntimeErrorCode.CIRCUIT_BREAKER_OPEN:
                return False

        if request.retry_policy == RetryPolicy.NONE:
            return False

        max_retries = min(self.config.max_retries, request.retry_limit)
        return attempts_made <= max_retries

    def get_retry_delay(self, request: WorkerInvocationRequest, attempts_made: int) -> float:
        """
        Calculate retry delay in seconds.
        """
        if request.retry_policy == RetryPolicy.NONE:
            return 0.0
        elif request.retry_policy == RetryPolicy.FIXED_DELAY:
            return 2.0
        elif request.retry_policy == RetryPolicy.EXPONENTIAL_BACKOFF:
            return float(self.config.backoff_factor * (2.0 ** (attempts_made - 1)))
        return 0.0

    def determine_failure_state(self, current_state: WorkflowState, error: Exception) -> WorkflowState:
        """Determine what state to transition to on fatal error."""
        return WorkflowState.FAILED

    def should_restore_checkpoint(self, attempts_made: int, error: Exception) -> bool:
        """Decide if we should restore from the last checkpoint to retry from scratch."""
        return False
