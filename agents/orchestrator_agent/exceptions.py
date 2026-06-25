# agents/orchestrator_agent/exceptions.py
"""
Exception hierarchy for the GrowthScout AI Orchestrator Agent.

Ownership: orchestrator_agent (sole authority for raising these)
Invariants:
  - Only unrecoverable infrastructure failures should raise these.
  - Validation failures return typed result objects; they do NOT raise.
  - All exceptions carry a human-readable message and an optional context payload.
"""


class OrchestratorBaseError(Exception):
    """
    Root base class for all orchestrator exceptions.

    Never catch this directly — prefer specific subclasses.
    """
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"


# ─── State Machine Errors ────────────────────────────────────────────────────

class InvalidTransitionError(OrchestratorBaseError):
    """
    Raised when the orchestrator attempts to commit a transition
    that was denied by the TransitionController.

    This is an infrastructure guard — it should only be raised if
    the caller ignores a TransitionResult with is_valid=False.
    """


# ─── Worker Invocation Errors ─────────────────────────────────────────────────

class WorkerNotFoundError(OrchestratorBaseError):
    """
    Raised when WorkerRegistry.get() is called with an unregistered worker name.
    """


class WorkerInvocationError(OrchestratorBaseError):
    """
    Raised when a worker agent invocation fails after all retries are exhausted.

    Attributes:
        worker_name: Name of the worker that failed.
        attempts: Number of invocation attempts made.
    """
    def __init__(self, message: str, worker_name: str, attempts: int = 1) -> None:
        super().__init__(message)
        self.worker_name = worker_name
        self.attempts = attempts


# ─── Evidence Validation Errors ──────────────────────────────────────────────

class EvidenceValidationError(OrchestratorBaseError):
    """
    Raised only when the orchestrator attempts to proceed to a state
    whose EvidenceRequirements are not satisfied AND the caller has
    explicitly chosen to treat validation failure as fatal.

    In normal flow, EvidenceValidationHook returns EvidenceValidationResult
    (a typed result object) and does NOT raise.
    """


# ─── Checkpoint Errors ────────────────────────────────────────────────────────

class CheckpointNotFoundError(OrchestratorBaseError):
    """
    Raised when CheckpointInterface.load() finds no checkpoint
    for the requested session_id.
    """


class CheckpointVersionConflictError(OrchestratorBaseError):
    """
    Raised when CheckpointInterface.save() is called with a
    checkpoint_version that is not strictly greater than the last saved version.
    """


# ─── Resumability Errors ──────────────────────────────────────────────────────

class WorkflowResumeError(OrchestratorBaseError):
    """
    Raised when ResumabilityController.resume() encounters an unrecoverable
    condition (e.g. schema version mismatch that cannot be auto-migrated).

    Normal non-resumable cases (terminal state, no checkpoint) return
    ResumeResult(resumed=False) and do NOT raise.
    """


# ─── Memory Permission Errors ─────────────────────────────────────────────────

class MemoryPermissionError(OrchestratorBaseError):
    """
    Raised only if the orchestrator explicitly escalates a denied
    MemoryDecision to a fatal error. In normal flow MemoryGovernor
    returns MemoryDecision(allowed=False) and does NOT raise.
    """


# ─── Audit Trail Errors ───────────────────────────────────────────────────────

class ImmutabilityViolationError(OrchestratorBaseError):
    """
    Raised when AuditTrailWriter.append() is called with an entry_id
    that already exists in the trail for a given session.
    """
