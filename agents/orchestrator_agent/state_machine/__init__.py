# agents/orchestrator_agent/state_machine/__init__.py
"""
State machine package for the GrowthScout AI Orchestrator Agent.

Exports the workflow state topology, canonical runtime context,
pure-validation transition controller, and advisory memory governor.
"""
from .states import (
    WorkflowState,
    StateType,
    EvidenceRequirement,
    StateNode,
    WORKFLOW_TOPOLOGY,
    TERMINAL_STATES,
    ACTIVE_STATES,
)
from .workflow_context import (
    WorkflowContext,
    EvidenceReference,
    PartitionSummary,
    ExecutionMetadata,
    WorkflowMetadata,
    WorkflowTimestamps,
)
from .transition_controller import (
    TransitionController,
    TransitionResult,
    TransitionValidationStatus,
    MemoryAction,
)
from .memory_governor import (
    MemoryGovernor,
    MemoryDecision,
)

__all__ = [
    # States
    "WorkflowState",
    "StateType",
    "EvidenceRequirement",
    "StateNode",
    "WORKFLOW_TOPOLOGY",
    "TERMINAL_STATES",
    "ACTIVE_STATES",
    # Context
    "WorkflowContext",
    "EvidenceReference",
    "PartitionSummary",
    "ExecutionMetadata",
    "WorkflowMetadata",
    "WorkflowTimestamps",
    # Transition
    "TransitionController",
    "TransitionResult",
    "TransitionValidationStatus",
    "MemoryAction",
    # Memory
    "MemoryGovernor",
    "MemoryDecision",
]
