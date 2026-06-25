# agents/orchestrator_agent/interfaces/worker_invocation.py
"""
Typed worker invocation contracts for the GrowthScout AI Orchestrator.

Ownership: orchestrator_agent (sole caller of WorkerRegistry and invocation contracts)

This module defines:
  - RetryPolicy — enum for retry strategies
  - WorkerInvocationRequest — strongly typed dispatch contract
  - WorkerInvocationResult — typed result wrapper
  - WorkerRegistry — lazy-import registry that maps names → LlmAgent instances

Invariants:
  - Workers are never imported at module load time (lazy import via WorkerRegistry.get())
    to prevent circular imports (workers import agents.shared.schemas).
  - Workers may not import each other; WorkerRegistry enforces single-name lookups only.
  - Workers receive only their required context fields — they never receive a full
    WorkflowContext directly (the orchestrator extracts and passes typed inputs).
  - WorkerInvocationRequest is frozen (immutable after construction).
"""
from __future__ import annotations

import importlib
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Type

from pydantic import BaseModel, Field

from ..exceptions import WorkerNotFoundError

# Type alias for LlmAgent — imported here only for type hints, not at runtime
# (avoids pulling all worker deps into orchestrator scope at import time)
_WORKER_MODULE_MAP: Dict[str, str] = {
    "business_discovery_agent": "agents.business_discovery_agent.agent",
    "website_analysis_agent":   "agents.website_analysis_agent.agent",
    "opportunity_agent":        "agents.opportunity_agent.agent",
    "growth_intelligence_agent": "agents.growth_intelligence_agent.agent",
}


# ─── RetryPolicy ─────────────────────────────────────────────────────────────

class RetryPolicy(str, Enum):
    """
    Retry strategy for worker invocations.

    NONE               — do not retry on failure
    FIXED_DELAY        — wait a fixed interval between retries
    EXPONENTIAL_BACKOFF — double the delay on each successive retry
    """
    NONE = "NONE"
    FIXED_DELAY = "FIXED_DELAY"
    EXPONENTIAL_BACKOFF = "EXPONENTIAL_BACKOFF"


# ─── WorkerInvocationRequest ──────────────────────────────────────────────────

class WorkerInvocationRequest(BaseModel):
    """
    Typed dispatch contract for an orchestrator → worker invocation.

    Ownership: orchestrator_agent creates these; WorkerRegistry resolves the agent.
    Inputs:
      worker_name:           Registered name of the target worker
      input_payload:         Typed Pydantic input model for the worker (not raw dict)
      input_keys:            Context keys the worker should use (informational)
      expected_output_schema: Name of the Pydantic output class expected
      timeout:               Max seconds before WorkerInvocationError is raised
      retry_limit:           Max retry attempts after first failure
      retry_policy:          Strategy for spacing retries
      correlation_id:        Ties this invocation to an audit trail entry
      execution_deadline:    Hard wall-clock cutoff for the invocation

    Invariant: timeout > 0, retry_limit >= 0
    """
    model_config = {"frozen": True}

    worker_name: str = Field(
        ...,
        description="Registered worker name in WorkerRegistry.",
    )
    input_payload: BaseModel = Field(
        ...,
        description="Typed Pydantic model carrying the worker's required inputs.",
    )
    input_keys: list[str] = Field(
        default_factory=list,
        description="WorkflowContext keys consumed by this invocation (informational).",
    )
    expected_output_schema: str = Field(
        ...,
        description="Name of the Pydantic output class the worker should return.",
    )
    timeout: float = Field(
        default=60.0,
        gt=0.0,
        description="Max seconds for the invocation before timeout error.",
    )
    retry_limit: int = Field(
        default=2,
        ge=0,
        description="Maximum number of retry attempts after initial failure.",
    )
    retry_policy: RetryPolicy = Field(
        default=RetryPolicy.EXPONENTIAL_BACKOFF,
        description="Strategy for spacing retry attempts.",
    )
    correlation_id: str = Field(
        ...,
        description="ID linking this invocation to its audit trail entry.",
    )
    execution_deadline: Optional[datetime] = Field(
        None,
        description="Optional hard wall-clock cutoff for the entire invocation.",
    )


# ─── WorkerInvocationResult ───────────────────────────────────────────────────

class WorkerInvocationResult(BaseModel):
    """
    Typed result of a completed (or failed) worker invocation.

    Inputs:  (returned by the orchestrator after agent runner execution)
    Outputs:
      worker_name:         Name of the worker that was invoked
      correlation_id:      Ties result to audit trail and request
      success:             True when output is non-null and schema-valid
      output:              Validated Pydantic output (None on failure)
      error_message:       Failure description (None on success)
      execution_duration_ms: Total invocation time in milliseconds
      retries_attempted:   Number of retry attempts made (0 = first attempt succeeded)
    """
    model_config = {"frozen": True}

    worker_name: str = Field(..., description="Name of the invoked worker.")
    correlation_id: str = Field(..., description="Links this result to its audit entry.")
    success: bool = Field(..., description="True when the worker returned valid output.")
    output: Optional[BaseModel] = Field(
        None,
        description="Validated Pydantic output model. None on failure.",
    )
    error_message: Optional[str] = Field(
        None,
        description="Failure description. None on success.",
    )
    execution_duration_ms: float = Field(
        ...,
        ge=0.0,
        description="Total invocation duration in milliseconds.",
    )
    retries_attempted: int = Field(
        ...,
        ge=0,
        description="Number of retry attempts made. 0 = success on first attempt.",
    )


# ─── WorkerRegistry ───────────────────────────────────────────────────────────

class WorkerRegistry:
    """
    Lazy-import registry mapping worker names to their LlmAgent instances.

    Ownership: instantiated by orchestrator agent.py and injected via DI.
    Inputs:    worker_name string
    Outputs:   LlmAgent instance

    Invariants:
      - Workers are imported lazily on first access to avoid circular imports.
      - Each registered worker maps to exactly one module path.
      - Workers cannot be cross-referenced from within WorkerRegistry
        (no worker can retrieve another worker through this registry).
      - WorkerNotFoundError is raised for unknown names (not KeyError).
    """

    def __init__(self) -> None:
        # Cache: worker_name → resolved LlmAgent instance
        self._cache: Dict[str, object] = {}

    def get(self, worker_name: str) -> object:
        """
        Return the LlmAgent for the given worker name.

        Args:
          worker_name: Registered name (e.g. "business_discovery_agent").

        Returns:
          LlmAgent instance.

        Raises:
          WorkerNotFoundError: If worker_name is not in the registry.
        """
        if worker_name not in _WORKER_MODULE_MAP:
            raise WorkerNotFoundError(
                f"Worker '{worker_name}' is not registered. "
                f"Known workers: {sorted(_WORKER_MODULE_MAP.keys())}"
            )

        if worker_name not in self._cache:
            module = importlib.import_module(_WORKER_MODULE_MAP[worker_name])
            self._cache[worker_name] = module.agent

        return self._cache[worker_name]

    def is_registered(self, worker_name: str) -> bool:
        """Return True if worker_name is a known registry entry."""
        return worker_name in _WORKER_MODULE_MAP

    def registered_names(self) -> list[str]:
        """Return sorted list of all registered worker names."""
        return sorted(_WORKER_MODULE_MAP.keys())
