# service/tests/test_contract_validation.py
"""
CI-ready contract validation tool and test suite for OpenAPI contract freeze.
Validates the current API spec against service/api/openapi_frozen.json.
Classifies changes as compatible, additive, deprecated, or breaking.
Fails if any breaking change is introduced.
"""

import json
import os
import pytest
from typing import Dict, Any, List, Tuple

FROZEN_SPEC_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "api", "openapi_frozen.json"
)


def load_frozen_spec() -> Dict[str, Any]:
    """Loads the frozen baseline OpenAPI specification."""
    if not os.path.exists(FROZEN_SPEC_PATH):
        raise FileNotFoundError(f"Frozen OpenAPI spec not found at: {FROZEN_SPEC_PATH}")
    with open(FROZEN_SPEC_PATH, "r") as f:
        return json.load(f)


def get_current_spec() -> Dict[str, Any]:
    """Generates the current OpenAPI spec from the live FastAPI app."""
    from service.main import app
    return app.openapi()


class OpenAPIContractDiffer:
    """
    Compares two OpenAPI specifications and classifies changes.
    Change types:
      - BREAKING: Deletions, type alterations, parameter modifications making fields required.
      - ADDITIVE: New routes, optional parameters, new schemas.
      - DEPRECATED: Explicit deprecated tags added.
      - COMPATIBLE: Description/summary updates, non-breaking schema additions.
    """
    def __init__(self, frozen: Dict[str, Any], current: Dict[str, Any]) -> None:
        self.frozen = frozen
        self.current = current
        self.breakages: List[str] = []
        self.additions: List[str] = []
        self.deprecations: List[str] = []
        self.compatibles: List[str] = []

    def diff_specs(self) -> Tuple[List[str], List[str], List[str], List[str]]:
        """Executes full diff suite across endpoints, operation IDs, security, and schemas."""
        self._diff_paths()
        self._diff_security_schemes()
        self._diff_schemas()
        return self.breakages, self.additions, self.deprecations, self.compatibles

    def _diff_paths(self):
        frozen_paths = self.frozen.get("paths", {})
        current_paths = self.current.get("paths", {})

        for path, frozen_path_item in frozen_paths.items():
            if path not in current_paths:
                self.breakages.append(f"Deleted path: {path}")
                continue

            current_path_item = current_paths[path]
            for method, frozen_op in frozen_path_item.items():
                if method not in current_path_item:
                    self.breakages.append(f"Deleted method: {method.upper()} on {path}")
                    continue

                current_op = current_path_item[method]
                
                # 1. Operation ID check
                frozen_op_id = frozen_op.get("operationId")
                current_op_id = current_op.get("operationId")
                if frozen_op_id != current_op_id:
                    self.breakages.append(
                        f"Modified operationId on {method.upper()} {path}: "
                        f"expected '{frozen_op_id}', got '{current_op_id}'"
                    )

                # 2. Summary/Description compatible changes
                if frozen_op.get("summary") != current_op.get("summary"):
                    self.compatibles.append(f"Updated summary on {method.upper()} {path}")
                if frozen_op.get("description") != current_op.get("description"):
                    self.compatibles.append(f"Updated description on {method.upper()} {path}")

                # 3. Parameters check
                self._diff_parameters(
                    path, method,
                    frozen_op.get("parameters", []),
                    current_op.get("parameters", [])
                )

                # 4. Request Body check
                self._diff_request_body(path, method, frozen_op.get("requestBody"), current_op.get("requestBody"))

                # 5. Responses check
                self._diff_responses(
                    path, method,
                    frozen_op.get("responses", {}),
                    current_op.get("responses", {})
                )

        # Look for new paths/methods (Additions)
        for path, current_path_item in current_paths.items():
            if path not in frozen_paths:
                self.additions.append(f"Added new path: {path}")
                continue
            for method in current_path_item:
                if method not in frozen_paths[path]:
                    self.additions.append(f"Added new method: {method.upper()} on {path}")

    def _diff_parameters(self, path: str, method: str, frozen_params: list, current_params: list):
        frozen_map = {p["name"]: p for p in frozen_params}
        current_map = {p["name"]: p for p in current_params}

        for name, fp in frozen_map.items():
            if name not in current_map:
                self.breakages.append(f"Deleted parameter '{name}' in {method.upper()} {path}")
                continue

            cp = current_map[name]
            # Check type changes
            if fp.get("schema", {}).get("type") != cp.get("schema", {}).get("type"):
                self.breakages.append(
                    f"Altered parameter type for '{name}' in {method.upper()} {path}: "
                    f"expected '{fp.get('schema', {}).get('type')}', got '{cp.get('schema', {}).get('type')}'"
                )
            # Check if optional parameter became required
            if not fp.get("required", False) and cp.get("required", False):
                self.breakages.append(f"Optional parameter '{name}' is now required in {method.upper()} {path}")

        # Check for new required parameters
        for name, cp in current_map.items():
            if name not in frozen_map:
                if cp.get("required", False):
                    self.breakages.append(f"Added new required parameter '{name}' to {method.upper()} {path}")
                else:
                    self.additions.append(f"Added new optional parameter '{name}' to {method.upper()} {path}")

    def _diff_request_body(self, path: str, method: str, frozen_body: Any, current_body: Any):
        if not frozen_body:
            if current_body:
                self.additions.append(f"Added request body to {method.upper()} {path}")
            return

        if not current_body:
            self.breakages.append(f"Deleted request body from {method.upper()} {path}")
            return

        # Diff ref structures if mapped to JSON schema
        frozen_ref = self._get_schema_ref(frozen_body)
        current_ref = self._get_schema_ref(current_body)
        if frozen_ref != current_ref:
            self.breakages.append(
                f"Altered request body schema mapping for {method.upper()} {path}: "
                f"expected '{frozen_ref}', got '{current_ref}'"
            )

    def _diff_responses(self, path: str, method: str, frozen_resps: dict, current_resps: dict):
        for code, fr in frozen_resps.items():
            if code not in current_resps:
                self.breakages.append(f"Deleted response status code '{code}' from {method.upper()} {path}")
                continue

            cr = current_resps[code]
            # Diff response schema reference
            frozen_ref = self._get_schema_ref(fr)
            current_ref = self._get_schema_ref(cr)
            if frozen_ref != current_ref:
                self.breakages.append(
                    f"Altered response schema mapping for status {code} on {method.upper()} {path}: "
                    f"expected '{frozen_ref}', got '{current_ref}'"
                )

        # Check for new responses
        for code in current_resps:
            if code not in frozen_resps:
                self.additions.append(f"Added new response status code '{code}' to {method.upper()} {path}")

    def _diff_security_schemes(self):
        frozen_schemes = self.frozen.get("components", {}).get("securitySchemes", {})
        current_schemes = self.current.get("components", {}).get("securitySchemes", {})

        for name, fs in frozen_schemes.items():
            if name not in current_schemes:
                self.breakages.append(f"Deleted security scheme: {name}")
                continue
            cs = current_schemes[name]
            if fs.get("type") != cs.get("type") or fs.get("name") != cs.get("name") or fs.get("in") != cs.get("in"):
                self.breakages.append(f"Altered security scheme configuration for '{name}'")

    def _diff_schemas(self):
        frozen_schemas = self.frozen.get("components", {}).get("schemas", {})
        current_schemas = self.current.get("components", {}).get("schemas", {})

        for name, fs in frozen_schemas.items():
            if name not in current_schemas:
                self.breakages.append(f"Deleted schema component: {name}")
                continue

            cs = current_schemas[name]
            frozen_props = fs.get("properties", {})
            current_props = cs.get("properties", {})

            for prop_name, fp in frozen_props.items():
                if prop_name not in current_props:
                    self.breakages.append(f"Deleted property '{prop_name}' from schema '{name}'")
                    continue

                cp = current_props[prop_name]
                # Validate type
                if fp.get("type") != cp.get("type"):
                    self.breakages.append(
                        f"Altered type for '{prop_name}' in schema '{name}': "
                        f"expected '{fp.get('type')}', got '{cp.get('type')}'"
                    )
                # Check deprecation
                if cp.get("deprecated") and not fp.get("deprecated"):
                    self.deprecations.append(f"Deprecated property '{prop_name}' in schema '{name}'")

            # Check for new required/optional properties
            frozen_req = fs.get("required", [])
            current_req = cs.get("required", [])
            for prop_name, cp in current_props.items():
                if prop_name not in frozen_props:
                    if prop_name in current_req:
                        self.breakages.append(f"Added new REQUIRED property '{prop_name}' to schema '{name}'")
                    else:
                        self.additions.append(f"Added new OPTIONAL property '{prop_name}' to schema '{name}'")

    def _get_schema_ref(self, item: dict) -> str:
        """Helper to extract reference from a request or response object."""
        try:
            content = item.get("content", {})
            schema = content.get("application/json", {}).get("schema", {})
            if "$ref" in schema:
                return schema["$ref"]
            if schema.get("type") == "array" and "$ref" in schema.get("items", {}):
                return f"Array[{schema['items']['$ref']}]"
        except Exception:
            pass
        return "unknown"


def _get_compatibility_report_json(breakages, additions, deprecations, compatibles) -> str:
    """Formats findings into a JSON string report."""
    report = {
        "compatibility_status": "COMPATIBLE" if not breakages else "BREAKING",
        "counts": {
            "breaking": len(breakages),
            "additive": len(additions),
            "deprecated": len(deprecations),
            "compatible": len(compatibles),
        },
        "details": {
            "breaking": breakages,
            "additive": additions,
            "deprecated": deprecations,
            "compatible": compatibles,
        }
    }
    return json.dumps(report, indent=2)


# ────────────────────────────────────────────────────────
# Test Suite
# ────────────────────────────────────────────────────────

def test_frozen_spec_file_exists():
    """Asserts the frozen openapi file is present."""
    assert os.path.exists(FROZEN_SPEC_PATH)


def test_openapi_spec_compatibility():
    """
    Diffs the current live spec against the frozen baseline openapi_frozen.json.
    Ensures that zero breaking changes are introduced.
    """
    frozen = load_frozen_spec()
    current = get_current_spec()

    differ = OpenAPIContractDiffer(frozen, current)
    breakages, additions, deprecations, compatibles = differ.diff_specs()

    # Generate test artifact report location
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "artifacts",
        "compatibility_report.json"
    )
    # Also write to local service directory for easy CI retrieval
    local_report_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "api",
        "compatibility_report_ci.json"
    )

    report_json = _get_compatibility_report_json(breakages, additions, deprecations, compatibles)
    
    # Save the reports
    os.makedirs(os.path.dirname(local_report_path), exist_ok=True)
    with open(local_report_path, "w") as f:
        f.write(report_json)

    # Assert no breakages
    if breakages:
        pytest.fail(
            f"API Contract compatibility validation failed with {len(breakages)} breaking changes!\n"
            f"Breakages:\n" + "\n".join(f"- {b}" for b in breakages)
        )
