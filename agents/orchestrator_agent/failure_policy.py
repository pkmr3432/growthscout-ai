# agents/orchestrator_agent/failure_policy.py
"""
FailurePolicy component for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent
Responsibility: Governs timeout handling, retry decisions, delays, and failure state routing.
"""
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from datetime import datetime, timezone

from .interfaces.worker_invocation import RetryPolicy, WorkerInvocationRequest
from .state_machine.states import WorkflowState

class FailurePolicy:
    """
    Failure policy governing retry, delay, recovery, and failure routing.

    Invariants:
      - Side-effect free (pure logic).
      - Dictates behavior to the WorkflowExecutor.
    """

    def should_retry(self, request: WorkerInvocationRequest, attempts_made: int) -> bool:
        """
        Determine if we should retry the invocation.

        Args:
          request: The request triggering the failure.
          attempts_made: The total attempts completed so far (1 for the first failure).
        """
        if request.retry_policy == RetryPolicy.NONE:
            return False
        return attempts_made <= request.retry_limit

    def get_retry_delay(self, request: WorkerInvocationRequest, attempts_made: int) -> float:
        """
        Calculate retry delay in seconds.

        NONE -> 0.0
        FIXED_DELAY -> 2.0 (or custom fixed amount)
        EXPONENTIAL_BACKOFF -> 2.0 * (2 ** (attempts_made - 1))
        """
        if request.retry_policy == RetryPolicy.NONE:
            return 0.0
        elif request.retry_policy == RetryPolicy.FIXED_DELAY:
            return 2.0
        elif request.retry_policy == RetryPolicy.EXPONENTIAL_BACKOFF:
            return 2.0 * (2.0 ** (attempts_made - 1))
        return 0.0

    def determine_failure_state(self, current_state: WorkflowState, error: Exception) -> WorkflowState:
        """Determine what state to transition to on fatal error."""
        return WorkflowState.FAILED

    def should_restore_checkpoint(self, attempts_made: int, error: Exception) -> bool:
        """Decide if we should restore from the last checkpoint to retry from scratch."""
        return False
