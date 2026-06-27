# service/tests/test_bootstrap.py
"""
Unit and integration tests for FastAPI bootstrap and routing foundation.
"""

import sys
import pytest
from fastapi.testclient import TestClient
from service.main import app

client = TestClient(app)

def test_health_endpoint():
    """Verifies liveness check returns HTTP 200 and healthy status with version metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data

def test_ready_endpoint():
    """Verifies readiness check returns HTTP 200 and ready or degraded status."""
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] in ["READY", "DEGRADED"]

def test_startup_check_endpoint():
    """Verifies startup check confirms compatible Python environments."""
    response = client.get("/startup-check")
    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    assert "python_version" in response.json()

def test_openapi_generation():
    """Verifies OpenAPI JSON schema compiles and contains endpoints metadata."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "paths" in schema
    # Assert root unversioned health routes exist
    assert "/health" in schema["paths"]
    assert "/ready" in schema["paths"]
    assert "/startup-check" in schema["paths"]
    # Assert versioned sessions routes exist
    assert "/api/v1/sessions" in schema["paths"]
    assert "/api/v1/sessions/{session_id}" in schema["paths"]

def test_session_creation_auth_check():
    """Verifies session operations reject requests missing X-API-Key."""
    payload = {
        "niche": "dental clinic",
        "location": "Boston, MA",
        "max_leads": 10
    }
    # Call without header -> FastAPI validates header existence and returns 400 Bad Request (via custom handler)
    response = client.post("/api/v1/sessions", json=payload)
    assert response.status_code == 400

def test_session_creation_invalid_auth():
    """Verifies session operations reject invalid API keys with 401 Unauthorized."""
    payload = {
        "niche": "dental clinic",
        "location": "Boston, MA",
        "max_leads": 10
    }
    response = client.post("/api/v1/sessions", json=payload, headers={"X-API-Key": "invalid_key"})
    assert response.status_code == 401
    assert "error" in response.json()
    assert response.json()["error"]["code"] == "AUTHENTICATION_FAILED"

def test_session_creation_success():
    """Verifies session creation returns 201 Created and valid response structures."""
    payload = {
        "niche": "dental clinic",
        "location": "Boston, MA",
        "max_leads": 10
    }
    response = client.post("/api/v1/sessions", json=payload, headers={"X-API-Key": "gs_dev_key_12345"})
    assert response.status_code == 201
    data = response.json()
    assert data["session_id"].startswith("sess_")
    assert data["workflow_id"].startswith("wf_")
    assert data["niche"] == "dental clinic"
    assert data["location"] == "Boston, MA"
    assert data["max_leads"] == 10
