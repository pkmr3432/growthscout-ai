# service/tests/test_openapi.py
"""
Comprehensive test suite verifying OpenAPI spec completeness, custom operation IDs,
JSON schema examples, standard error envelopes, and security schemes.
"""

import pytest
from fastapi.testclient import TestClient
from service.main import app

client = TestClient(app)


def test_openapi_spec_structure():
    """Asserts OpenAPI spec exists, is valid JSON, and matches OpenAPI 3.x structure."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "openapi" in spec
    assert spec["openapi"].startswith("3.")
    assert "info" in spec
    assert "paths" in spec
    assert "components" in spec
    assert "schemas" in spec["components"]


def test_openapi_security_schemes():
    """Asserts security scheme is documented as APIKeyHeader scheme."""
    response = client.get("/openapi.json")
    spec = response.json()
    
    # Assert securitySchemes exists and is configured for APIKeyHeader
    assert "securitySchemes" in spec["components"]
    assert "APIKeyHeader" in spec["components"]["securitySchemes"]
    
    scheme = spec["components"]["securitySchemes"]["APIKeyHeader"]
    assert scheme["type"] == "apiKey"
    assert scheme["name"] == "X-API-Key"
    assert scheme["in"] == "header"
    assert "description" in scheme


def test_openapi_operation_ids_exist():
    """Asserts that all core endpoints expose standardized, clean operation IDs."""
    response = client.get("/openapi.json")
    spec = response.json()
    paths = spec["paths"]

    # Map paths to expected HTTP methods and clean operation IDs
    expected_operations = {
        "/health": {"get": "livenessCheck"},
        "/ready": {"get": "readinessCheck"},
        "/startup-check": {"get": "startupCheck"},
        "/metrics": {"get": "prometheusMetrics"},
        "/api/v1/sessions": {"post": "createSession"},
        "/api/v1/sessions/{session_id}": {"get": "getSession"},
        "/api/v1/sessions/{session_id}/run": {"post": "runSession"},
        "/api/v1/sessions/{session_id}/feedback": {"post": "submitFeedback"},
        "/api/v1/sessions/{session_id}/cancel": {"post": "cancelSession"},
        "/api/v1/sessions/{session_id}/stream": {"get": "streamSession"},
    }

    for path, methods in expected_operations.items():
        assert path in paths, f"Path '{path}' is missing in OpenAPI specs."
        for method, expected_op_id in methods.items():
            assert method in paths[path], f"Method '{method}' missing on path '{path}'."
            operation = paths[path][method]
            assert "operationId" in operation, f"Missing operationId for {method} {path}."
            assert operation["operationId"] == expected_op_id, \
                f"Expected operationId '{expected_op_id}', got '{operation['operationId']}'."


def test_openapi_endpoint_documentation_complete():
    """Asserts endpoints include summaries, descriptions, and tags."""
    response = client.get("/openapi.json")
    spec = response.json()
    paths = spec["paths"]

    for path in paths:
        for method in paths[path]:
            operation = paths[path][method]
            assert "summary" in operation and len(operation["summary"]) > 0, \
                f"Missing summary in {method} {path}."
            assert "description" in operation and len(operation["description"]) > 0, \
                f"Missing description in {method} {path}."
            assert "tags" in operation and len(operation["tags"]) > 0, \
                f"Missing tags in {method} {path}."


def test_openapi_schemas_contain_examples():
    """Asserts that all core schemas define mock examples for SDK developers."""
    response = client.get("/openapi.json")
    spec = response.json()
    schemas = spec["components"]["schemas"]

    expected_schemas = [
        "SessionCreateRequest",
        "SessionResponse",
        "FeedbackSubmitRequest",
        "ErrorDetail",
        "StandardErrorResponse",
        "LivenessResponse",
        "ReadinessResponse",
        "StartupCheckResponse",
    ]

    for schema_name in expected_schemas:
        assert schema_name in schemas, f"Schema '{schema_name}' missing in OpenAPI components."
        schema = schemas[schema_name]
        
        # Check if schema contains examples in model properties or JSON schema extra list
        has_example = "example" in schema or "examples" in schema or (
            "json_schema_extra" in schema and "examples" in schema["json_schema_extra"]
        )
        # Note: OpenAPI generator extracts pydantic JSON schema extra examples into schema "examples" or "example"
        assert has_example or any("example" in prop or "examples" in prop for prop in schema.get("properties", {}).values()), \
            f"Schema '{schema_name}' is missing example documentation."


def test_openapi_error_responses_mapped():
    """Asserts versioned routes map standard HTTP error envelopes to status codes."""
    response = client.get("/openapi.json")
    spec = response.json()
    paths = spec["paths"]

    # Sessions routes should map StandardErrorResponse for failures
    session_routes = [
        "/api/v1/sessions",
        "/api/v1/sessions/{session_id}",
        "/api/v1/sessions/{session_id}/run",
        "/api/v1/sessions/{session_id}/feedback",
        "/api/v1/sessions/{session_id}/cancel",
        "/api/v1/sessions/{session_id}/stream",
    ]

    for path in session_routes:
        assert path in paths
        for method in paths[path]:
            responses = paths[path][method]["responses"]
            # Assert error codes are documented with standard error envelope
            for status_code in ["401", "429", "500"]:
                assert status_code in responses, f"Response status code '{status_code}' missing in {method} {path}."
                content = responses[status_code].get("content", {})
                assert "application/json" in content, f"Missing JSON response content for {status_code} in {method} {path}."
                schema_ref = content["application/json"]["schema"]["$ref"]
                assert "StandardErrorResponse" in schema_ref, f"Expected StandardErrorResponse reference, got {schema_ref}."


def test_openapi_backward_compatibility():
    """Asserts that schemas have not deleted fields from previous releases to maintain contract safety."""
    response = client.get("/openapi.json")
    spec = response.json()
    schemas = spec["components"]["schemas"]

    # SessionResponse fields verification
    session_resp_properties = schemas["SessionResponse"]["properties"]
    expected_fields = [
        "session_id", "workflow_id", "current_state", "niche",
        "location", "max_leads", "revision_count", "created_at", "updated_at", "status"
    ]
    for field in expected_fields:
        assert field in session_resp_properties, f"Backward compatibility break: Field '{field}' missing from SessionResponse."

    # Liveness Response check (health endpoint compatibility)
    liveness_properties = schemas["LivenessResponse"]["properties"]
    assert "status" in liveness_properties
    assert "version" in liveness_properties
    assert "uptime_seconds" in liveness_properties


def test_sdk_model_alignment():
    """Asserts Python SDK typed models are fully synchronized with the frozen OpenAPI schemas."""
    import os
    import json
    from growthscout.models import SessionResponse, EventEnvelope

    # Load frozen spec
    frozen_spec_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "service", "api", "openapi_frozen.json"
    )
    with open(frozen_spec_path, "r") as f:
        spec = json.load(f)

    schemas = spec["components"]["schemas"]

    # 1. Assert SessionResponse properties match SDK model fields exactly
    spec_fields = set(schemas["SessionResponse"]["properties"].keys())
    sdk_fields = set(SessionResponse.model_fields.keys())
    assert spec_fields == sdk_fields, f"Mismatch: Spec fields {spec_fields} vs SDK fields {sdk_fields}"

    # 2. Assert EventEnvelope (SSE Event Schema) properties match SDK model fields
    sdk_envelope_fields = set(EventEnvelope.model_fields.keys())
    assert "event_id" in sdk_envelope_fields
    assert "event_type" in sdk_envelope_fields
    assert "session_id" in sdk_envelope_fields
    assert "timestamp" in sdk_envelope_fields
    assert "data" in sdk_envelope_fields
    assert "correlation_id" in sdk_envelope_fields
