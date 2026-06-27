# service/api/schemas/v1/events.py
"""
Canonical Server-Sent Event envelope models for streaming workflow execution events.

Every SSE event emitted by the service layer conforms to the EventEnvelope schema,
ensuring consistent structure for clients, replay buffers, and observability tooling.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """
    Registry of canonical SSE event types emitted during workflow execution.
    """
    EXECUTION_STARTED = "execution_started"
    STATE_CHANGED = "state_changed"
    STEP_COMPLETED = "step_completed"
    GATE_REACHED = "gate_reached"
    EXECUTION_COMPLETED = "execution_completed"
    EXECUTION_FAILED = "execution_failed"
    EXECUTION_CANCELLED = "execution_cancelled"
    HEARTBEAT = "heartbeat"
    STREAM_CONNECTED = "stream_connected"
    STREAM_ENDED = "stream_ended"


class EventEnvelope(BaseModel):
    """
    Canonical envelope wrapping every SSE event dispatched to subscribers.

    Fields:
        event_id: Monotonically increasing integer scoped per session stream.
        event_type: Canonical event type from the EventType registry.
        session_id: Workflow session this event belongs to.
        timestamp: UTC ISO-8601 timestamp of event creation.
        data: Arbitrary structured payload specific to the event type.
        correlation_id: Optional request correlation ID for tracing.
    """
    event_id: int = Field(..., description="Monotonically increasing event sequence number")
    event_type: EventType = Field(..., description="Canonical event type identifier")
    session_id: str = Field(..., description="Session ID this event belongs to")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        description="UTC ISO-8601 timestamp"
    )
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific payload data")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID for tracing")

    def to_sse_format(self) -> str:
        """
        Formats this event as a valid SSE text/event-stream message.

        Output:
            id: {event_id}
            event: {event_type}
            data: {json_payload}
        """
        import json
        payload = self.model_dump(mode="json")
        lines = [
            f"id: {self.event_id}",
            f"event: {self.event_type.value}",
            f"data: {json.dumps(payload)}",
            "",  # Trailing blank line terminates the SSE message
            ""
        ]
        return "\n".join(lines)
