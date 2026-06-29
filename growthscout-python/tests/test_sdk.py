# growthscout-python/tests/test_sdk.py
"""
Unit tests for the GrowthScout AI Python SDK.
Verifies client validation, exceptions mapping, retries, and serialization.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from growthscout import (
    GrowthScout,
    GrowthScoutAuthenticationError,
    GrowthScoutValidationError,
    GrowthScoutRateLimitError,
    GrowthScoutLockConflictError,
    GrowthScoutPayloadTooLargeError,
    GrowthScoutNetworkError
)


def test_client_init_requires_key():
    """Asserts that instantiation raises error on missing or invalid API keys."""
    with pytest.raises(GrowthScoutAuthenticationError):
        GrowthScout(api_key="")
    with pytest.raises(GrowthScoutAuthenticationError):
        GrowthScout(api_key=None)


@pytest.mark.anyio
@patch("httpx.AsyncClient.request")
async def test_client_exception_mapping(mock_request):
    """Verifies that standard HTTP error codes map to specific SDK exception classes."""
    client = GrowthScout(api_key="test_key")

    error_mappings = [
        (400, GrowthScoutValidationError),
        (401, GrowthScoutAuthenticationError),
        (403, GrowthScoutAuthenticationError),
        (404, GrowthScoutValidationError),
        (409, GrowthScoutLockConflictError),
        (413, GrowthScoutPayloadTooLargeError),
        (429, GrowthScoutRateLimitError),
    ]

    for status_code, exc_class in error_mappings:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.text = "Error detail"
        mock_response.json.return_value = {"error": {"message": "Fail", "code": "FAIL"}}
        
        mock_request.return_value = mock_response

        with pytest.raises(exc_class):
            await client.sessions.get("sess_123")


@pytest.mark.anyio
@patch("httpx.AsyncClient.request")
async def test_client_retry_middleware_success(mock_request):
    """Verifies transient connection failures (network errors) trigger retry loop."""
    client = GrowthScout(api_key="test_key", max_retries=2)

    # Trigger httpx timeout twice, then succeed
    mock_request.side_effect = [
        httpx.TimeoutException("Timeout"),
        httpx.TimeoutException("Timeout"),
        MagicMock(status_code=200, json=lambda: {"session_id": "sess_123", "workflow_id": "wf_123", "current_state": "idle", "niche": "test", "location": "test", "max_leads": 5, "revision_count": 0, "created_at": "2026-06-27T00:00:00Z", "updated_at": "2026-06-27T00:00:00Z", "status": "idle"})
    ]

    # Temporarily patch sleep to speed up tests
    with patch("asyncio.sleep", return_value=None):
        session = await client.sessions.get("sess_123")
        assert session.session_id == "sess_123"
        assert mock_request.call_count == 3


@pytest.mark.anyio
@patch("httpx.AsyncClient.request")
async def test_client_retry_middleware_max_attempts_exceeded(mock_request):
    """Verifies failure raised if network retries exceed max_retries limit."""
    client = GrowthScout(api_key="test_key", max_retries=2)

    mock_request.side_effect = httpx.TimeoutException("Timeout")

    with patch("asyncio.sleep", return_value=None):
        with pytest.raises(GrowthScoutNetworkError):
            await client.sessions.get("sess_123")
        assert mock_request.call_count == 3  # Initial + 2 retries


@pytest.mark.anyio
@patch("httpx.AsyncClient.request")
async def test_client_never_retries_client_errors(mock_request):
    """Verifies client errors (400, 401, 409, etc.) fail fast without retrying."""
    client = GrowthScout(api_key="test_key", max_retries=2)

    mock_response = MagicMock()
    mock_response.status_code = 409
    mock_response.text = "Session locked"
    mock_response.json.return_value = {"error": {"message": "Session locked", "code": "SESSION_LOCKED"}}
    
    mock_request.return_value = mock_response

    with pytest.raises(GrowthScoutLockConflictError):
        await client.sessions.run("sess_123")
    
    assert mock_request.call_count == 1  # Fails fast, no retries


@pytest.mark.anyio
@patch("httpx.AsyncClient.request")
async def test_client_pagination_params_passed(mock_request):
    """Verifies pagination helper passes correct limit and offset query parameters."""
    client = GrowthScout(api_key="test_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_request.return_value = mock_response

    await client.sessions.list_sessions(limit=10, offset=20)
    
    # Assert correct parameters were mapped
    _, kwargs = mock_request.call_args
    assert kwargs["params"] == {"limit": 10, "offset": 20}
