# agents/orchestrator_agent/interfaces/__init__.py
"""
Interfaces package for the GrowthScout AI Orchestrator Agent.

Exports typed contracts for worker invocation, checkpoint persistence,
workflow resumability, and the event publication interface.
"""
from .worker_invocation import (
    WorkerRegistry,
    WorkerInvocationRequest,
    WorkerInvocationResult,
    WorkerExecutionResult,
    RetryPolicy,
)
from .checkpoint import (
    CheckpointInterface,
    WorkflowCheckpoint,
)
from .resumability import (
    ResumabilityController,
    ResumeResult,
)
from .events import (
    WorkflowEvent,
    EventPublisher,
    WorkerCompleted,
    WorkerFailed,
    TransitionExecuted,
    MemoryWritten,
    CheckpointSaved,
    WorkflowPaused,
    WorkflowResumed,
)

__all__ = [
    # Worker invocation
    "WorkerRegistry",
    "WorkerInvocationRequest",
    "WorkerInvocationResult",
    "WorkerExecutionResult",
    "RetryPolicy",
    # Checkpoint
    "CheckpointInterface",
    "WorkflowCheckpoint",
    # Resumability
    "ResumabilityController",
    "ResumeResult",
    # Events
    "WorkflowEvent",
    "EventPublisher",
    "WorkerCompleted",
    "WorkerFailed",
    "TransitionExecuted",
    "MemoryWritten",
    "CheckpointSaved",
    "WorkflowPaused",
    "WorkflowResumed",
]
