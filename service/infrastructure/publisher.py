# service/infrastructure/publisher.py
"""
Event publisher abstractions and production SSE-compatible implementation
with bounded replay buffers, monotonic event IDs, and heartbeat support.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Set, Any, AsyncGenerator, Optional

from service.api.schemas.v1.events import EventEnvelope, EventType

logger = logging.getLogger("growthscout.publisher")

# Default configuration constants
DEFAULT_REPLAY_BUFFER_SIZE = 256
DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0


class EventPublisher(ABC):
    """
    Interface for publishing and subscribing to workflow execution events.
    """
    @abstractmethod
    async def publish(self, session_id: str, event_name: str, data: Dict[str, Any],
                      correlation_id: Optional[str] = None) -> None:
        """
        Publishes an event to a session subscriber pool.
        """
        pass

    @abstractmethod
    async def subscribe(self, session_id: str,
                        last_event_id: Optional[int] = None) -> AsyncGenerator[EventEnvelope, None]:
        """
        Subscribes to live events for a session, returning an async generator.
        Supports replay from last_event_id for reconnection.
        """
        pass

    @abstractmethod
    async def close_session(self, session_id: str) -> None:
        """
        Signals all subscribers that the session stream has ended and cleans up resources.
        """
        pass


class SSEPublisher(EventPublisher):
    """
    In-memory pub/sub registry coordinating Server-Sent Events (SSE) subscribers.

    Features:
        - Monotonically increasing event IDs per session
        - Bounded replay buffer for Last-Event-ID reconnection
        - Heartbeat-aware subscriber generators
        - Graceful session close with STREAM_ENDED sentinel
    """
    def __init__(
        self,
        replay_buffer_size: int = DEFAULT_REPLAY_BUFFER_SIZE,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    ) -> None:
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._event_counters: Dict[str, int] = {}
        self._replay_buffers: Dict[str, deque] = {}
        self._lock = asyncio.Lock()
        self._replay_buffer_size = replay_buffer_size
        self._heartbeat_interval = heartbeat_interval

    async def publish(self, session_id: str, event_name: str, data: Dict[str, Any],
                      correlation_id: Optional[str] = None) -> None:
        """
        Publishes an event, assigns a monotonic ID, stores in replay buffer,
        and dispatches to all active subscribers.
        """
        async with self._lock:
            # Assign monotonic event ID
            if session_id not in self._event_counters:
                self._event_counters[session_id] = 0
            self._event_counters[session_id] += 1
            event_id = self._event_counters[session_id]

            # Resolve EventType
            try:
                event_type = EventType(event_name)
            except ValueError:
                event_type = EventType.STATE_CHANGED

            # Build canonical envelope
            envelope = EventEnvelope(
                event_id=event_id,
                event_type=event_type,
                session_id=session_id,
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                data=data,
                correlation_id=correlation_id
            )

            # Store in bounded replay buffer
            if session_id not in self._replay_buffers:
                self._replay_buffers[session_id] = deque(maxlen=self._replay_buffer_size)
            self._replay_buffers[session_id].append(envelope)

            # Dispatch to all active subscriber queues
            if session_id in self._subscribers:
                for queue in self._subscribers[session_id]:
                    try:
                        queue.put_nowait(envelope)
                    except asyncio.QueueFull:
                        logger.warning(f"Subscriber queue full for session {session_id}, dropping event {event_id}")

    async def subscribe(self, session_id: str,
                        last_event_id: Optional[int] = None) -> AsyncGenerator[EventEnvelope, None]:
        """
        Subscribes to live events for a session.
        If last_event_id is provided, replays missed events from the bounded buffer first.
        Emits a STREAM_CONNECTED event and generates heartbeat events at the configured interval.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = set()
            self._subscribers[session_id].add(queue)

        try:
            # Emit STREAM_CONNECTED event
            connected_envelope = EventEnvelope(
                event_id=0,
                event_type=EventType.STREAM_CONNECTED,
                session_id=session_id,
                data={"message": "SSE stream established", "replay_from": last_event_id}
            )
            yield connected_envelope

            # Replay missed events if last_event_id is specified
            if last_event_id is not None:
                async with self._lock:
                    buffer = self._replay_buffers.get(session_id, deque())
                    for envelope in buffer:
                        if envelope.event_id > last_event_id:
                            yield envelope

            # Main event loop with heartbeat
            while True:
                try:
                    envelope = await asyncio.wait_for(queue.get(), timeout=self._heartbeat_interval)
                    yield envelope
                    queue.task_done()

                    # If STREAM_ENDED sentinel received, terminate
                    if envelope.event_type == EventType.STREAM_ENDED:
                        return

                except asyncio.TimeoutError:
                    # Emit heartbeat on timeout
                    heartbeat_id = self._event_counters.get(session_id, 0) + 1
                    heartbeat = EventEnvelope(
                        event_id=heartbeat_id,
                        event_type=EventType.HEARTBEAT,
                        session_id=session_id,
                        data={"message": "keepalive"}
                    )
                    yield heartbeat

        except asyncio.CancelledError:
            logger.info(f"SSE subscription for session {session_id} cancelled.")
            return
        finally:
            # Clean up subscriber queue
            async with self._lock:
                if session_id in self._subscribers:
                    self._subscribers[session_id].discard(queue)
                    if not self._subscribers[session_id]:
                        self._subscribers.pop(session_id, None)

    async def close_session(self, session_id: str) -> None:
        """
        Publishes a STREAM_ENDED sentinel, then clears the replay buffer and event counter.
        """
        await self.publish(
            session_id=session_id,
            event_name=EventType.STREAM_ENDED.value,
            data={"message": "Execution stream closed"}
        )
        # Cleanup session resources after a short delay allowing subscribers to drain
        await asyncio.sleep(0.1)
        async with self._lock:
            self._event_counters.pop(session_id, None)
            self._replay_buffers.pop(session_id, None)

    def get_subscriber_count(self, session_id: str) -> int:
        """
        Returns the count of active subscribers for a session (used for metrics).
        """
        return len(self._subscribers.get(session_id, set()))

    def get_event_count(self, session_id: str) -> int:
        """
        Returns the current monotonic event counter for a session.
        """
        return self._event_counters.get(session_id, 0)

    async def cancel_all(self) -> None:
        """
        Cleanup for graceful shutdown — close all active sessions.
        """
        async with self._lock:
            session_ids = list(self._subscribers.keys())
        for sid in session_ids:
            await self.close_session(sid)
