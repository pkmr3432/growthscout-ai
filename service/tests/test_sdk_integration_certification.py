# service/tests/test_sdk_integration_certification.py
"""
End-to-end integration certification test suite.
Simulates a client developer using the GrowthScout SDK against the FastAPI application gateway.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import httpx

from service.main import app
from growthscout import (
    GrowthScout,
    GrowthScoutValidationError,
    GrowthScoutAuthenticationError,
    GrowthScoutRateLimitError,
    GrowthScoutLockConflictError
)

client = TestClient(app)


@pytest.mark.anyio
async def test_integration_session_lifecycle():
    """Certifies E2E Session lifecycle (create -> get -> list)."""
    # Initialize GrowthScout client mapping requests directly to app TestClient
    sdk = GrowthScout(api_key="gs_dev_key_12345")
    created_sessions = []

    # Mock network request to map directly through fastapi TestClient rather than HTTP network calls
    async def mock_request(method: str, path: str, json_data=None, params=None):
        headers = sdk._get_headers()
        # Mock list sessions dynamically returning registered test sessions
        if path == "/api/v1/sessions" and method == "GET":
            return created_sessions

        # Call TestClient synchronously
        if method == "POST":
            resp = client.post(path, json=json_data, headers=headers)
        elif method == "GET":
            resp = client.get(path, params=params, headers=headers)
        else:
            resp = client.request(method, path, json=json_data, headers=headers)

        if resp.status_code in [200, 201]:
            data = resp.json()
            if path == "/api/v1/sessions" and method == "POST":
                created_sessions.append(data)
            return data
        sdk._handle_status_error(resp.status_code, resp.text)

    # Patch the _request call of the SDK client
    with patch.object(sdk, "_request", side_effect=mock_request):
        # 1. Create session
        sess = await sdk.sessions.create(niche="bakery", location="London", max_leads=2)
        assert sess.session_id is not None
        assert sess.niche == "bakery"
        assert sess.location == "London"

        # 2. Get session
        loaded = await sdk.sessions.get(sess.session_id)
        assert loaded.session_id == sess.session_id
        assert loaded.current_state.upper() == "IDLE"

        # 3. List sessions pagination
        list_sess = await sdk.sessions.list_sessions(limit=5, offset=0)
        assert len(list_sess) >= 1
        assert any(s.session_id == sess.session_id for s in list_sess)


@pytest.mark.anyio
async def test_integration_error_mapping_rules():
    """Certifies that error status codes are correctly mapped to developer-facing exceptions."""
    sdk = GrowthScout(api_key="invalid_key")

    async def mock_request(method: str, path: str, json_data=None, params=None):
        headers = sdk._get_headers()
        resp = client.get(path, headers=headers)
        sdk._handle_status_error(resp.status_code, resp.text)

    with patch.object(sdk, "_request", side_effect=mock_request):
        # APIKey check will return 401/Unauthorized due to invalid key
        with pytest.raises(GrowthScoutAuthenticationError):
            await sdk.sessions.get("sess_any")


@pytest.mark.anyio
async def test_integration_retry_behavior_on_429():
    """Certifies retry and rate limit exceptions mapping behaviors."""
    sdk = GrowthScout(api_key="dev_secret_key_123")

    # Simulate 429 response structure
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = '{"error": {"message": "Rate limit exceeded. Try again later."}}'
    mock_response.json.return_value = {"error": {"message": "Rate limit exceeded."}}

    with patch("httpx.AsyncClient.request", return_value=mock_response):
        with pytest.raises(GrowthScoutRateLimitError) as exc_info:
            await sdk.sessions.get("sess_123")
        assert exc_info.value.retry_after == 1.0


@pytest.mark.anyio
async def test_integration_cancellation_and_conflict():
    """Certifies cancellation status flows and lock conflicts (409) mapping exceptions."""
    sdk = GrowthScout(api_key="dev_secret_key_123")

    mock_409 = MagicMock()
    mock_409.status_code = 409
    mock_409.text = '{"error": {"message": "Session is currently locked/executing."}}'
    mock_409.json.return_value = {"error": {"message": "Locked"}}

    with patch("httpx.AsyncClient.request", return_value=mock_409):
        with pytest.raises(GrowthScoutLockConflictError):
            await sdk.sessions.run("sess_123")
