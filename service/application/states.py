# service/application/states.py
"""
Workflow Session state machine and transition governance.
"""

from enum import Enum
from typing import Set, Dict

class SessionState(str, Enum):
    CREATED = "CREATED"
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    WAITING_FOR_FEEDBACK = "WAITING_FOR_FEEDBACK"
    RESUMING = "RESUMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Valid transition mappings enforcing sequential lifecycle execution
_ALLOWED_TRANSITIONS: Dict[SessionState, Set[SessionState]] = {
    SessionState.CREATED: {SessionState.IDLE, SessionState.FAILED},
    SessionState.IDLE: {SessionState.RUNNING, SessionState.CANCELLED, SessionState.FAILED},
    SessionState.RUNNING: {
        SessionState.WAITING_FOR_FEEDBACK,
        SessionState.COMPLETED,
        SessionState.FAILED,
        SessionState.CANCELLED
    },
    SessionState.WAITING_FOR_FEEDBACK: {
        SessionState.RESUMING,
        SessionState.CANCELLED,
        SessionState.FAILED
    },
    SessionState.RESUMING: {
        SessionState.RUNNING,
        SessionState.FAILED,
        SessionState.CANCELLED
    },
    SessionState.COMPLETED: set(),
    SessionState.FAILED: set(),
    SessionState.CANCELLED: set(),
}

class InvalidStateTransitionError(ValueError):
    """Raised when an invalid state transition is requested."""
    def __init__(self, current_state: SessionState, target_state: SessionState) -> None:
        self.current_state = current_state
        self.target_state = target_state
        super().__init__(
            f"Invalid transition: Cannot move session from '{current_state.value}' "
            f"to '{target_state.value}'."
        )

def validate_transition(current: SessionState, target: SessionState) -> None:
    """
    Validates if a transition from current to target is allowed.
    Raises InvalidStateTransitionError if unauthorized.
    """
    if current == target:
        return
    if target not in _ALLOWED_TRANSITIONS.get(current, set()):
        raise InvalidStateTransitionError(current, target)
