# service/tests/test_execution.py
"""
Unit and integration tests for execution scheduling, locking, states, and checkpoints.
"""

import os
import asyncio
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

from service.main import app
from service.infrastructure.registry import registry
from service.infrastructure.config import settings
from service.application.states import SessionState, validate_transition, InvalidStateTransitionError
from service.application.lock_manager import SessionLockManager
from service.application.scheduler import TaskScheduler
from service.infrastructure.checkpoint import LocalCheckpointStore
from service.api.dependencies import get_execution_service

AUTH_HEADERS = {"X-API-Key": "gs_dev_key_12345"}

@pytest.mark.anyio
async def test_checkpoint_store_local(tmp_path):
    """Verifies LocalCheckpointStore persists, loads, and deletes checkpoints."""
    store = LocalCheckpointStore(checkpoint_dir=str(tmp_path))
    session_id = "sess_test_checkpoint"
    payload = {"test": "data", "status": "active"}

    # Assert load returns None for missing
    assert await store.load_checkpoint(session_id) is None

    # Save and load
    await store.save_checkpoint(session_id, payload)
    data = await store.load_checkpoint(session_id)
    assert data["test"] == "data"
    assert data["status"] == "active"

    # Delete
    await store.delete_checkpoint(session_id)
    assert await store.load_checkpoint(session_id) is None

@pytest.mark.anyio
async def test_session_lock_manager():
    """Verifies SessionLockManager lock states, acquisitions, and releases."""
    mgr = SessionLockManager()
    session_id = "sess_lock_test"

    # Initially unlocked
    assert not await mgr.is_locked(session_id)

    # Acquire lock
    assert await mgr.acquire(session_id) is True
    assert await mgr.is_locked(session_id) is True

    # Second acquisition fails
    assert await mgr.acquire(session_id) is False

    # Release
    await mgr.release(session_id)
    assert not await mgr.is_locked(session_id)

@pytest.mark.anyio
async def test_task_scheduler_cancellation():
    """Verifies TaskScheduler wraps coroutines, handles cancellation, and removes tasks."""
    scheduler = TaskScheduler()
    session_id = "sess_sched_test"

    async def long_coro():
        await asyncio.sleep(10)

    # Schedule task
    assert await scheduler.schedule_task(session_id, long_coro()) is True
    assert await scheduler.is_task_running(session_id) is True

    # Cancel task
    assert await scheduler.cancel_task(session_id) is True
    await asyncio.sleep(0.1) # yield control to run callbacks
    assert not await scheduler.is_task_running(session_id)

@pytest.mark.anyio
async def test_task_scheduler_timeout():
    """Verifies TaskScheduler handles execution timeouts correctly."""
    scheduler = TaskScheduler()
    session_id = "sess_timeout_test"

    async def slow_coro():
        await asyncio.sleep(2)

    # Schedule with 0.1s timeout
    done_called = False
    def on_done(t):
        nonlocal done_called
        done_called = True

    await scheduler.schedule_task(session_id, slow_coro(), timeout_seconds=0.1, on_done=on_done)
    await asyncio.sleep(0.3)
    
    assert not await scheduler.is_task_running(session_id)
    assert done_called is True

def test_invalid_state_transitions():
    """Verifies transition validator throws errors on invalid SessionState movements."""
    # Valid
    validate_transition(SessionState.CREATED, SessionState.IDLE)
    validate_transition(SessionState.IDLE, SessionState.RUNNING)
    validate_transition(SessionState.RUNNING, SessionState.WAITING_FOR_FEEDBACK)

    # Invalid
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(SessionState.COMPLETED, SessionState.RUNNING)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(SessionState.CREATED, SessionState.COMPLETED)

@pytest.mark.anyio
async def test_api_session_creation_and_run():
    """Verifies HTTP API endpoints for session creation and execution run."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Session
        response = await client.post(
            "/api/v1/sessions",
            json={"niche": "plumbing", "location": "Miami, FL", "max_leads": 5},
            headers=AUTH_HEADERS
        )
        assert response.status_code == 201
        session_id = response.json()["session_id"]
        assert response.json()["current_state"] == "IDLE"

        # 2. Run Session
        response = await client.post(f"/api/v1/sessions/{session_id}/run", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert response.json()["current_state"] == "RUNNING"
        
        # Cleanup task
        await registry.task_scheduler.cancel_task(session_id)

@pytest.mark.anyio
async def test_api_concurrency_lock_conflict():
    """Verifies that calling /run on an active session ID yields HTTP 409 Conflict."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Session
        response = await client.post(
            "/api/v1/sessions",
            json={"niche": "plumbing", "location": "Miami, FL", "max_leads": 5},
            headers=AUTH_HEADERS
        )
        session_id = response.json()["session_id"]

        # Trigger run 1
        response = await client.post(f"/api/v1/sessions/{session_id}/run", headers=AUTH_HEADERS)
        assert response.status_code == 200

        # Trigger run 2 concurrently -> Blocked by session locks returning 409 Conflict
        response = await client.post(f"/api/v1/sessions/{session_id}/run", headers=AUTH_HEADERS)
        assert response.status_code == 409
        data = response.json()
        assert data["error"]["code"] == "SESSION_LOCKED"
        assert "request_id" in data["error"]
        assert "timestamp" in data["error"]
        
        # Cleanup
        await registry.task_scheduler.cancel_task(session_id)

@pytest.mark.anyio
async def test_api_invalid_transition():
    """Verifies invalid transitions trigger HTTP 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Session
        response = await client.post(
            "/api/v1/sessions",
            json={"niche": "plumbing", "location": "Miami, FL", "max_leads": 5},
            headers=AUTH_HEADERS
        )
        session_id = response.json()["session_id"]

        # Session is in IDLE. Attempt feedback POST (which is only valid in WAITING_FOR_FEEDBACK)
        response = await client.post(
            f"/api/v1/sessions/{session_id}/feedback",
            json={"approved": True, "feedback_notes": "All good"},
            headers=AUTH_HEADERS
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_TRANSITION"

@pytest.mark.anyio
async def test_api_cancel_workflow():
    """Verifies HTTP API endpoint cancels actively running tasks."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Session
        response = await client.post(
            "/api/v1/sessions",
            json={"niche": "plumbing", "location": "Miami, FL", "max_leads": 5},
            headers=AUTH_HEADERS
        )
        session_id = response.json()["session_id"]

        # Run
        await client.post(f"/api/v1/sessions/{session_id}/run", headers=AUTH_HEADERS)

        # Cancel
        response = await client.post(f"/api/v1/sessions/{session_id}/cancel", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert response.json()["current_state"] == "CANCELLED"
