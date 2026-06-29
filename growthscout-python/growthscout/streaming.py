# growthscout-python/growthscout/streaming.py
"""
SSE Event Stream consumer for Python SDK.
"""

import asyncio
import json
import logging
import httpx
from typing import AsyncGenerator, Optional
from datetime import datetime

from growthscout.exceptions import GrowthScoutNetworkError, GrowthScoutError
from growthscout.models import EventEnvelope

logger = logging.getLogger("growthscout.streaming")


class EventStream:
    """
    Parses incoming HTTP text/event-stream chunks into typed EventEnvelope objects.
    Supports reconnection logic with exponential backoff using the Last-Event-ID header.
    """
    def __init__(self, client, session_id: str) -> None:
        self.client = client
        self.session_id = session_id
        self.last_event_id: Optional[int] = None
        self.active = True

    async def listen(self) -> AsyncGenerator[EventEnvelope, None]:
        url = f"{self.client.base_url}/api/v1/sessions/{self.session_id}/stream"
        attempt = 0

        while self.active:
            headers = self.client._get_headers()
            if self.last_event_id is not None:
                headers["Last-Event-ID"] = str(self.last_event_id)

            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", url, headers=headers) as response:
                        if response.status_code != 200:
                            self.client._handle_status_error(response.status_code, response.text)

                        # Successfully connected, reset retry attempt count
                        attempt = 0
                        buffer = ""
                        async for chunk in response.aiter_text():
                            if not self.active:
                                break
                            buffer += chunk
                            while "\n\n" in buffer:
                                block, buffer = buffer.split("\n\n", 1)
                                envelope = self._parse_block(block)
                                if envelope:
                                    self.last_event_id = envelope.event_id
                                    yield envelope
                                    if envelope.event_type == "stream_ended":
                                        self.active = False
                                        return

            except httpx.HTTPError as e:
                if not self.active:
                    break
                attempt += 1
                if attempt > self.client.max_retries:
                    raise GrowthScoutNetworkError(f"Reconnection failed after {attempt} attempts: {e}")

                sleep_time = min(10.0, 1.0 * (2 ** attempt))
                logger.warning(f"Connection dropped. Retrying in {sleep_time}s (attempt {attempt})...")
                await asyncio.sleep(sleep_time)

            except Exception as e:
                raise GrowthScoutError(f"Streaming error occurred: {e}")

    def close(self) -> None:
        """Closes the stream listener."""
        self.active = False

    def _parse_block(self, block: str) -> Optional[EventEnvelope]:
        lines = block.strip().split("\n")
        event_id = None
        event_type = None
        data = None

        for line in lines:
            if line.startswith("id:"):
                try:
                    event_id = int(line[3:].strip())
                except ValueError:
                    pass
            elif line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    pass

        if event_id is not None and event_type and data is not None:
            # Reconstruct envelope model
            # Skip heartbeats or return them as raw envelopes
            return EventEnvelope(
                event_id=event_id,
                event_type=event_type,
                session_id=data.get("session_id", self.session_id),
                timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat())),
                data=data.get("data", {}),
                correlation_id=data.get("correlation_id")
            )
        return None
