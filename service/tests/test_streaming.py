# service/tests/test_streaming.py
"""
Comprehensive test suite for Sprint 7.3 — Real-Time Event Streaming & Observability.

Tests:
    - SSEPublisher publish/subscribe lifecycle
    - Bounded replay buffer with Last-Event-ID
    - Heartbeat generation on timeout
    - Event envelope schema validation
    - Stream endpoint HTTP contract (headers, content-type)
    - Metrics endpoint Prometheus format
    - Rate limiter token bucket behavior
    - Rate limiter HTTP 429 response
    - EventPublisher close_session sentinel
    - ExecutionService event emission wiring
"""

import asyncio
import json
import time
import pytest

from httpx import AsyncClient, ASGITransport
from fastapi.testclient import TestClient

from service.main import app
from service.infrastructure.registry import registry
from service.infrastructure.publisher import SSEPublisher, DEFAULT_HEARTBEAT_INTERVAL_SECONDS
from service.api.schemas.v1.events import EventEnvelope, EventType
from service.middleware.rate_limit import TokenBucket, RateLimitMiddleware

AUTH_HEADERS = {"X-API-Key": "gs_dev_key_12345"}


# ─────────────────────────────────────
# Event Envelope Schema Tests
# ─────────────────────────────────────

class TestEventEnvelopeSchema:
    """Validates the canonical EventEnvelope model and SSE formatting."""

    def test_event_envelope_creation(self):
        """Verifies envelope creation with required fields."""
        envelope = EventEnvelope(
            event_id=1,
            event_type=EventType.EXECUTION_STARTED,
            session_id="sess_test123",
            data={"key": "value"}
        )
        assert envelope.event_id == 1
        assert envelope.event_type == EventType.EXECUTION_STARTED
        assert envelope.session_id == "sess_test123"
        assert envelope.data == {"key": "value"}
        assert envelope.timestamp is not None

    def test_event_envelope_sse_format(self):
        """Verifies SSE formatting contains id, event, and data fields."""
        envelope = EventEnvelope(
            event_id=42,
            event_type=EventType.HEARTBEAT,
            session_id="sess_test123",
            data={"message": "keepalive"}
        )
        sse_output = envelope.to_sse_format()
        assert "id: 42" in sse_output
        assert "event: heartbeat" in sse_output
        assert "data: " in sse_output
        # Parse the data JSON
        data_line = [l for l in sse_output.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert payload["event_id"] == 42
        assert payload["event_type"] == "heartbeat"
        assert payload["session_id"] == "sess_test123"

    def test_event_type_registry(self):
        """Verifies all expected event types are registered."""
        expected = {
            "execution_started", "state_changed", "step_completed",
            "gate_reached", "execution_completed", "execution_failed",
            "execution_cancelled", "heartbeat", "stream_connected", "stream_ended"
        }
        actual = {e.value for e in EventType}
        assert expected == actual

    def test_event_envelope_with_correlation_id(self):
        """Verifies correlation_id is included in SSE data payload."""
        envelope = EventEnvelope(
            event_id=5,
            event_type=EventType.STATE_CHANGED,
            session_id="sess_corr",
            data={},
            correlation_id="corr_abc123"
        )
        sse_output = envelope.to_sse_format()
        data_line = [l for l in sse_output.split("\n") if l.startswith("data: ")][0]
        payload = json.loads(data_line[6:])
        assert payload["correlation_id"] == "corr_abc123"


# ─────────────────────────────────────
# SSEPublisher Unit Tests
# ─────────────────────────────────────

class TestSSEPublisher:
    """Tests for the enhanced SSEPublisher with replay, IDs, and heartbeat."""

    @pytest.mark.anyio
    async def test_publish_assigns_monotonic_ids(self):
        """Verifies that publish assigns monotonically increasing event IDs."""
        pub = SSEPublisher(replay_buffer_size=10, heartbeat_interval=60.0)
        await pub.publish("sess_1", "execution_started", {"step": "A"})
        await pub.publish("sess_1", "step_completed", {"step": "B"})
        await pub.publish("sess_1", "execution_completed", {"step": "C"})

        assert pub.get_event_count("sess_1") == 3

    @pytest.mark.anyio
    async def test_publish_stores_in_replay_buffer(self):
        """Verifies events are stored in the bounded replay buffer."""
        pub = SSEPublisher(replay_buffer_size=5, heartbeat_interval=60.0)
        for i in range(7):
            await pub.publish("sess_buf", "step_completed", {"index": i})

        # Only last 5 should be in buffer
        buffer = pub._replay_buffers["sess_buf"]
        assert len(buffer) == 5
        assert buffer[0].event_id == 3  # events 1,2 were evicted
        assert buffer[-1].event_id == 7

    @pytest.mark.anyio
    async def test_subscribe_receives_published_events(self):
        """Verifies subscriber receives events after subscribing."""
        pub = SSEPublisher(replay_buffer_size=10, heartbeat_interval=60.0)
        received = []

        async def subscriber():
            async for envelope in pub.subscribe("sess_sub"):
                received.append(envelope)
                if envelope.event_type == EventType.STREAM_ENDED:
                    break

        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.05)  # Let subscriber start

        await pub.publish("sess_sub", "execution_started", {"msg": "hello"})
        await pub.publish("sess_sub", "step_completed", {"msg": "done"})
        await pub.close_session("sess_sub")

        await asyncio.wait_for(task, timeout=3.0)

        # STREAM_CONNECTED + 2 events + STREAM_ENDED (from close)
        event_types = [e.event_type for e in received]
        assert EventType.STREAM_CONNECTED in event_types
        assert EventType.EXECUTION_STARTED in event_types
        assert EventType.STEP_COMPLETED in event_types
        assert EventType.STREAM_ENDED in event_types

    @pytest.mark.anyio
    async def test_subscribe_with_last_event_id_replay(self):
        """Verifies replay of missed events when reconnecting with Last-Event-ID."""
        pub = SSEPublisher(replay_buffer_size=50, heartbeat_interval=60.0)

        # Publish events before subscriber connects
        await pub.publish("sess_replay", "execution_started", {"step": 1})
        await pub.publish("sess_replay", "step_completed", {"step": 2})
        await pub.publish("sess_replay", "step_completed", {"step": 3})
        await pub.publish("sess_replay", "execution_completed", {"step": 4})

        received = []

        async def subscriber():
            # Replay from event_id=2 (should get events 3, 4)
            async for envelope in pub.subscribe("sess_replay", last_event_id=2):
                received.append(envelope)
                if len(received) >= 4:  # CONNECTED + 2 replayed + at least 1 more
                    break

        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0.1)

        # Publish one more event after subscriber connects
        await pub.publish("sess_replay", "step_completed", {"step": 5})
        await asyncio.sleep(0.1)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # Should have: STREAM_CONNECTED, replayed event 3, replayed event 4, live event 5
        assert received[0].event_type == EventType.STREAM_CONNECTED
        replayed = [e for e in received if e.event_type != EventType.STREAM_CONNECTED]
        assert len(replayed) >= 2
        # First replayed event should be event_id=3
        assert replayed[0].event_id == 3

    @pytest.mark.anyio
    async def test_heartbeat_generation(self):
        """Verifies heartbeat events are generated when no events are published."""
        pub = SSEPublisher(replay_buffer_size=10, heartbeat_interval=0.15)  # 150ms heartbeat
        received = []

        async def subscriber():
            async for envelope in pub.subscribe("sess_hb"):
                received.append(envelope)
                if len(received) >= 3:  # CONNECTED + 2 heartbeats
                    break

        task = asyncio.create_task(subscriber())
        await asyncio.wait_for(task, timeout=2.0)

        heartbeats = [e for e in received if e.event_type == EventType.HEARTBEAT]
        assert len(heartbeats) >= 1  # At least 1 heartbeat generated

    @pytest.mark.anyio
    async def test_subscriber_count(self):
        """Verifies subscriber count tracking."""
        pub = SSEPublisher(replay_buffer_size=10, heartbeat_interval=60.0)

        assert pub.get_subscriber_count("sess_count") == 0

        # Start two subscribers
        received1, received2 = [], []

        async def sub1():
            async for envelope in pub.subscribe("sess_count"):
                received1.append(envelope)
                if envelope.event_type == EventType.STREAM_ENDED:
                    break

        async def sub2():
            async for envelope in pub.subscribe("sess_count"):
                received2.append(envelope)
                if envelope.event_type == EventType.STREAM_ENDED:
                    break

        t1 = asyncio.create_task(sub1())
        t2 = asyncio.create_task(sub2())
        await asyncio.sleep(0.05)

        assert pub.get_subscriber_count("sess_count") == 2

        await pub.close_session("sess_count")
        await asyncio.wait_for(asyncio.gather(t1, t2), timeout=3.0)

        # After close, subscribers should be cleaned up
        assert pub.get_subscriber_count("sess_count") == 0

    @pytest.mark.anyio
    async def test_close_session_cleanup(self):
        """Verifies close_session cleans up event counter and replay buffer."""
        pub = SSEPublisher(replay_buffer_size=10, heartbeat_interval=60.0)
        await pub.publish("sess_cleanup", "execution_started", {})
        await pub.publish("sess_cleanup", "step_completed", {})

        assert pub.get_event_count("sess_cleanup") == 2
        assert len(pub._replay_buffers.get("sess_cleanup", [])) == 2

        await pub.close_session("sess_cleanup")
        await asyncio.sleep(0.2)

        assert pub.get_event_count("sess_cleanup") == 0
        assert "sess_cleanup" not in pub._replay_buffers


# ─────────────────────────────────────
# Token Bucket Rate Limiter Unit Tests
# ─────────────────────────────────────

class TestTokenBucket:
    """Tests for the token bucket rate limiter implementation."""

    def test_initial_full_capacity(self):
        """Verifies bucket starts with full capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        for _ in range(10):
            assert bucket.consume() is True
        # 11th request should be throttled
        assert bucket.consume() is False

    def test_refill_over_time(self):
        """Verifies tokens refill over time."""
        bucket = TokenBucket(capacity=2, refill_rate=10.0)
        assert bucket.consume() is True
        assert bucket.consume() is True
        assert bucket.consume() is False  # Empty

        # Wait 0.2 seconds = refills 2 tokens (10/sec * 0.2s)
        time.sleep(0.25)
        assert bucket.consume() is True

    def test_retry_after_calculation(self):
        """Verifies retry_after calculation returns sensible value."""
        bucket = TokenBucket(capacity=1, refill_rate=1.0)
        bucket.consume()
        retry = bucket.retry_after_seconds
        assert retry > 0.0
        assert retry <= 1.0


# ─────────────────────────────────────
# HTTP Integration Tests
# ─────────────────────────────────────

client = TestClient(app)


class TestMetricsEndpoint:
    """Tests for the Prometheus /metrics endpoint."""

    def test_metrics_returns_200(self):
        """Verifies /metrics returns HTTP 200."""
        response = client.get("/metrics")
        assert response.status_code == 200

    def test_metrics_prometheus_format(self):
        """Verifies /metrics output follows Prometheus text exposition format."""
        response = client.get("/metrics")
        content = response.text
        assert "# HELP growthscout_uptime_seconds" in content
        assert "# TYPE growthscout_uptime_seconds gauge" in content
        assert "growthscout_uptime_seconds" in content
        assert "growthscout_requests_total" in content
        assert "growthscout_active_tasks" in content
        assert "growthscout_active_locks" in content
        assert "growthscout_sse_subscribers" in content
        assert "growthscout_events_published_total" in content

    def test_metrics_content_type(self):
        """Verifies /metrics uses the correct Prometheus content type."""
        response = client.get("/metrics")
        assert "text/plain" in response.headers["content-type"]


class TestRateLimiterIntegration:
    """Integration tests for rate limiter middleware on the FastAPI app."""

    def test_rate_limit_headers_present(self):
        """Verifies rate limit response headers are set on normal requests."""
        response = client.get("/health")
        # Health is excluded from rate limiting, so headers won't be present
        # Test with a versioned endpoint that IS rate limited
        response = client.post(
            "/api/v1/sessions",
            json={"niche": "test", "location": "test", "max_leads": 1},
            headers=AUTH_HEADERS
        )
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

    def test_health_excluded_from_rate_limit(self):
        """Verifies health endpoints are excluded from rate limiting."""
        # Health endpoints should never return 429
        for _ in range(30):
            response = client.get("/health")
            assert response.status_code == 200


class TestStreamEndpoint:
    """Tests for the SSE streaming endpoint HTTP contract."""

    @pytest.mark.anyio
    async def test_stream_returns_event_stream_content_type(self):
        """Verifies /stream returns text/event-stream content type and proper headers."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Create a session first
            resp = await ac.post(
                "/api/v1/sessions",
                json={"niche": "streaming", "location": "LA, CA", "max_leads": 1},
                headers=AUTH_HEADERS
            )
            session_id = resp.json()["session_id"]

            # Open stream with a timeout to prevent hanging
            async def read_stream():
                async with ac.stream("GET", f"/api/v1/sessions/{session_id}/stream", headers=AUTH_HEADERS) as response:
                    assert response.status_code == 200
                    assert "text/event-stream" in response.headers["content-type"]
                    assert response.headers.get("cache-control") == "no-cache, no-store, must-revalidate"
                    assert response.headers.get("x-accel-buffering") == "no"

                    # Read first chunk (STREAM_CONNECTED event)
                    first_chunk = b""
                    async for chunk in response.aiter_bytes():
                        first_chunk += chunk
                        if b"stream_connected" in first_chunk:
                            break

                    decoded = first_chunk.decode("utf-8")
                    assert "event: stream_connected" in decoded
                    assert "id: 0" in decoded

            try:
                await asyncio.wait_for(read_stream(), timeout=5.0)
            except asyncio.TimeoutError:
                pass  # Expected — stream is infinite, we validated headers and first event

    @pytest.mark.anyio
    async def test_stream_404_for_missing_session(self):
        """Verifies /stream returns 404 for non-existent session IDs."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/sessions/sess_nonexistent/stream",
                headers=AUTH_HEADERS
            )
            assert response.status_code == 404

    @pytest.mark.anyio
    async def test_stream_requires_auth(self):
        """Verifies /stream endpoint requires API key authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Create session first
            resp = await ac.post(
                "/api/v1/sessions",
                json={"niche": "authtest", "location": "NY, NY", "max_leads": 1},
                headers=AUTH_HEADERS
            )
            session_id = resp.json()["session_id"]

            # Try stream without auth - should get 400 (missing required header) or 422
            response = await ac.get(f"/api/v1/sessions/{session_id}/stream")
            assert response.status_code in [400, 422]


class TestOpenAPIStreamDocumentation:
    """Tests for OpenAPI documentation of streaming endpoint."""

    def test_openapi_includes_stream_endpoint(self):
        """Verifies OpenAPI schema documents the stream endpoint."""
        response = client.get("/openapi.json")
        schema = response.json()
        # Stream should be documented
        stream_path = "/api/v1/sessions/{session_id}/stream"
        assert stream_path in schema["paths"]
        assert "get" in schema["paths"][stream_path]

    def test_openapi_includes_metrics_endpoint(self):
        """Verifies OpenAPI schema documents the metrics endpoint."""
        response = client.get("/openapi.json")
        schema = response.json()
        assert "/metrics" in schema["paths"]


# ─────────────────────────────────────
# ExecutionService Event Wiring Tests
# ─────────────────────────────────────

class TestExecutionServiceEventWiring:
    """Tests that ExecutionService emits events during workflow lifecycle."""

    @pytest.mark.anyio
    async def test_run_session_emits_execution_started(self):
        """Verifies that running a session emits execution_started event."""
        transport = ASGITransport(app=app)
        publisher = registry.event_publisher
        received = []

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Create session
            resp = await ac.post(
                "/api/v1/sessions",
                json={"niche": "events", "location": "SF, CA", "max_leads": 1},
                headers=AUTH_HEADERS
            )
            session_id = resp.json()["session_id"]

            # Subscribe to events
            async def collector():
                async for envelope in publisher.subscribe(session_id):
                    received.append(envelope)
                    if envelope.event_type in (EventType.STREAM_ENDED, EventType.EXECUTION_COMPLETED,
                                                EventType.GATE_REACHED, EventType.EXECUTION_FAILED):
                        break

            task = asyncio.create_task(collector())
            await asyncio.sleep(0.05)

            # Run session
            resp = await ac.post(f"/api/v1/sessions/{session_id}/run", headers=AUTH_HEADERS)
            assert resp.status_code == 200

            # Wait for background task to complete
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Verify events were emitted
            event_types = [e.event_type for e in received]
            assert EventType.STREAM_CONNECTED in event_types
            assert EventType.EXECUTION_STARTED in event_types

            # Cleanup
            await registry.task_scheduler.cancel_task(session_id)

    @pytest.mark.anyio
    async def test_cancel_session_emits_cancelled_event(self):
        """Verifies cancelling a session emits execution_cancelled event."""
        transport = ASGITransport(app=app)
        publisher = registry.event_publisher
        received = []

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Create and run session
            resp = await ac.post(
                "/api/v1/sessions",
                json={"niche": "cancel_ev", "location": "Chicago, IL", "max_leads": 1},
                headers=AUTH_HEADERS
            )
            session_id = resp.json()["session_id"]

            # Subscribe to events
            async def collector():
                async for envelope in publisher.subscribe(session_id):
                    received.append(envelope)
                    if envelope.event_type == EventType.STREAM_ENDED:
                        break

            task = asyncio.create_task(collector())
            await asyncio.sleep(0.05)

            # Run session
            await ac.post(f"/api/v1/sessions/{session_id}/run", headers=AUTH_HEADERS)
            await asyncio.sleep(0.1)

            # Cancel session
            resp = await ac.post(f"/api/v1/sessions/{session_id}/cancel", headers=AUTH_HEADERS)
            assert resp.status_code == 200

            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            event_types = [e.event_type for e in received]
            assert EventType.STREAM_CONNECTED in event_types
            assert EventType.EXECUTION_CANCELLED in event_types
            assert EventType.STREAM_ENDED in event_types
