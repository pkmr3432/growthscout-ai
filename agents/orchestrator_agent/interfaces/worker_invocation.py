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
import sys
import os
import yaml
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Type, Any, List, Callable

from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from ..exceptions import WorkerNotFoundError
from ..runtime_config import RuntimeConfig
from agents.shared.schemas import (
    DiscoveryLeadsSchema,
    AuditResultsSchema,
    OpportunityAnalysisSchema,
    GrowthReportsSchema,
)

# Root directory can be resolved dynamically
_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DIR = os.path.abspath(os.path.join(_AGENT_DIR, "..", ".."))

# Type alias for LlmAgent — imported here only for type hints, not at runtime
# (avoids pulling all worker deps into orchestrator scope at import time)
_WORKER_MODULE_MAP: Dict[str, str] = {
    "business_discovery_agent": "agents.business_discovery_agent.agent",
    "website_analysis_agent":   "agents.website_analysis_agent.agent",
    "opportunity_agent":        "agents.opportunity_agent.agent",
    "growth_intelligence_agent": "agents.growth_intelligence_agent.agent",
}


# ─── Dynamic Worker Builders ──────────────────────────────────────────────────

def _load_agent_data(agent_folder: str) -> tuple[dict, str]:
    folder_path = os.path.join(_ROOT_DIR, "agents", agent_folder)
    config_path = os.path.join(folder_path, "definition.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["agent"]

    policy_dir = os.path.join(_ROOT_DIR, "agents", "shared", "policies")
    policies = []
    for policy_file in ["safety_policy.md", "evidence_policy.md", "grounding_policy.md"]:
        p_path = os.path.join(policy_dir, policy_file)
        if os.path.exists(p_path):
            with open(p_path, "r") as pf:
                policies.append(pf.read())
    policy_text = "\n\n".join(policies)
    system_instruction = f"{config['system_instruction']}\n\n=== SHARED POLICIES ===\n{policy_text}"
    return config, system_instruction


def _build_discovery_agent(config: RuntimeConfig) -> LlmAgent:
    cfg, system_instruction = _load_agent_data("business_discovery_agent")
    
    local_search_mcp = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "servers.local_search_server.server"],
                env={
                    "GOOGLE_MAPS_API_KEY": config.google_maps_api_key,
                    "GEMINI_API_KEY": config.gemini_api_key,
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": os.environ.get("PYTHONPATH", "") or ".",
                }
            )
        ),
        tool_filter=["local_business_search"]
    )
    
    return LlmAgent(
        name=cfg["name"],
        model=cfg["model"],
        instruction=system_instruction,
        description=cfg["description"],
        tools=[local_search_mcp],
        output_schema=DiscoveryLeadsSchema,
        output_key="leads"
    )


def _build_website_analysis_agent(config: RuntimeConfig) -> LlmAgent:
    cfg, system_instruction = _load_agent_data("website_analysis_agent")
    
    web_analyzer_mcp = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=["-m", "servers.web_analyzer_server.server"],
                env={
                    "GOOGLE_MAPS_API_KEY": config.google_maps_api_key,
                    "GEMINI_API_KEY": config.gemini_api_key,
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONPATH": os.environ.get("PYTHONPATH", "") or ".",
                }
            )
        ),
        tool_filter=["web_page_fetcher", "tech_footprint_scanner", "seo_auditor"]
    )
    
    return LlmAgent(
        name=cfg["name"],
        model=cfg["model"],
        instruction=system_instruction,
        description=cfg["description"],
        tools=[web_analyzer_mcp],
        output_schema=AuditResultsSchema,
        output_key="audit_results"
    )


def _build_opportunity_agent(config: RuntimeConfig) -> LlmAgent:
    cfg, system_instruction = _load_agent_data("opportunity_agent")
    return LlmAgent(
        name=cfg["name"],
        model=cfg["model"],
        instruction=system_instruction,
        description=cfg["description"],
        tools=[],
        output_schema=OpportunityAnalysisSchema,
        output_key="opportunities"
    )


def _build_growth_intelligence_agent(config: RuntimeConfig) -> LlmAgent:
    cfg, system_instruction = _load_agent_data("growth_intelligence_agent")
    return LlmAgent(
        name=cfg["name"],
        model=cfg["model"],
        instruction=system_instruction,
        description=cfg["description"],
        tools=[],
        output_schema=GrowthReportsSchema,
        output_key="growth_reports"
    )


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
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings generated during validation/normalization.",
    )


# ─── WorkerExecutionResult ───────────────────────────────────────────────────

class WorkerExecutionResult(BaseModel):
    """
    Standardized worker execution result model.
    """
    model_config = {"frozen": True}

    success: bool = Field(..., description="True if execution was successful.")
    worker_name: str = Field(..., description="Name of the worker agent.")
    output: Optional[BaseModel] = Field(None, description="Pydantic output schema model or None.")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Metrics delta/recorded.")
    evidence: list[Any] = Field(default_factory=list, description="Evidence generated/collected.")
    runtime: float = Field(..., description="Execution duration in seconds.")
    retries: int = Field(..., description="Number of retries attempted.")
    warnings: list[str] = Field(default_factory=list, description="Warnings generated during run.")
    correlation_id: str = Field(..., description="Correlation ID tying invocation to audit/trace.")



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

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self.config = config
        # Factories: worker_name -> factory Callable
        self._factories: Dict[str, Callable[[], object]] = {}
        # Cache: worker_name -> resolved LlmAgent instance
        self._cache: Dict[str, object] = {}
        self._register_default_factories()

    def _register_default_factories(self) -> None:
        if self.config and self.config.google_maps_api_key and self.config.gemini_api_key:
            self.register("business_discovery_agent", lambda: _build_discovery_agent(self.config))
            self.register("website_analysis_agent", lambda: _build_website_analysis_agent(self.config))
            self.register("opportunity_agent", lambda: _build_opportunity_agent(self.config))
            self.register("growth_intelligence_agent", lambda: _build_growth_intelligence_agent(self.config))
        else:
            for name in _WORKER_MODULE_MAP:
                self.register(name, lambda n=name: self._default_factory(n))

    def _default_factory(self, worker_name: str) -> object:
        module = importlib.import_module(_WORKER_MODULE_MAP[worker_name])
        return module.agent

    def register(self, worker_name: str, factory: Callable[[], object]) -> None:
        """Register a worker factory for lazy instantiation."""
        self._factories[worker_name] = factory

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
        if worker_name not in self._factories and worker_name not in _WORKER_MODULE_MAP:
            raise WorkerNotFoundError(
                f"Worker '{worker_name}' is not registered. "
                f"Known workers: {sorted(list(self._factories.keys()) or _WORKER_MODULE_MAP.keys())}"
            )

        if worker_name not in self._factories:
            self.register(worker_name, lambda n=worker_name: self._default_factory(n))

        if worker_name not in self._cache:
            factory = self._factories[worker_name]
            self._cache[worker_name] = factory()

        return self._cache[worker_name]

    def is_registered(self, worker_name: str) -> bool:
        """Return True if worker_name is a known registry entry."""
        return worker_name in self._factories or worker_name in _WORKER_MODULE_MAP

    def registered_names(self) -> list[str]:
        """Return sorted list of all registered worker names."""
        keys = set(self._factories.keys()) | set(_WORKER_MODULE_MAP.keys())
        return sorted(list(keys))
