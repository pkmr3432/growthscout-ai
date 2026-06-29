# service/tests/test_sdk_packaging.py
"""
Automated validation checks verifying SDK packaging parameters, manifest files,
documentation completeness, and version consistency.
"""

import json
import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def test_sdk_version_consistency():
    """Asserts that version metadata is consistent across API Spec, Python SDK, and TS SDK."""
    # 1. Load OpenAPI spec version
    openapi_spec_path = os.path.join(ROOT_DIR, "service", "api", "openapi_frozen.json")
    assert os.path.exists(openapi_spec_path)
    with open(openapi_spec_path, "r") as f:
        spec = json.load(f)
    openapi_version = spec.get("info", {}).get("version", "unknown")

    # 2. Load Python SDK version
    pyproject_path = os.path.join(ROOT_DIR, "growthscout-python", "pyproject.toml")
    assert os.path.exists(pyproject_path)
    with open(pyproject_path, "r") as f:
        pyproject_content = f.read()
    py_version_match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
    assert py_version_match, "Failed to parse Python version from pyproject.toml"
    py_version = py_version_match.group(1)

    # 3. Load TypeScript SDK version
    package_json_path = os.path.join(ROOT_DIR, "growthscout-js", "package.json")
    assert os.path.exists(package_json_path)
    with open(package_json_path, "r") as f:
        package_json = json.load(f)
    ts_version = package_json.get("version", "unknown")

    # Assert all versions are exactly aligned
    assert py_version == ts_version, f"SDK version mismatch: Python ({py_version}) vs TypeScript ({ts_version})"
    
    # Allow development spec version fallback
    if openapi_version != "0.0.0-dev":
        assert py_version in openapi_version or openapi_version in py_version, \
            f"SDK version ({py_version}) does not align with API spec version ({openapi_version})"


def test_documentation_completeness():
    """Asserts that both SDK README files contain critical usage sections to prevent documentation drift."""
    required_sections = [
        "Installation",
        "Quick Start",
        "Authentication",
        "SSE Streaming",
        "Exception Handling"
    ]

    readme_paths = [
        os.path.join(ROOT_DIR, "growthscout-python", "README.md"),
        os.path.join(ROOT_DIR, "growthscout-js", "README.md")
    ]

    for path in readme_paths:
        assert os.path.exists(path), f"README missing at: {path}"
        with open(path, "r") as f:
            content = f.read()
        for section in required_sections:
            # Check for header or text match (case-insensitive)
            assert re.search(re.escape(section), content, re.IGNORECASE), \
                f"Missing documentation section '{section}' in README: {path}"


def test_typescript_packaging_manifest():
    """Asserts package.json declares ESM and CommonJS exports correctly."""
    package_json_path = os.path.join(ROOT_DIR, "growthscout-js", "package.json")
    assert os.path.exists(package_json_path)
    with open(package_json_path, "r") as f:
        package_json = json.load(f)

    assert "main" in package_json
    assert "module" in package_json
    assert "types" in package_json
    assert "exports" in package_json
    assert "." in package_json["exports"]
    assert "import" in package_json["exports"]["."]
    assert "require" in package_json["exports"]["."]


def test_python_packaging_manifest():
    """Asserts pyproject.toml defines poetry layout and dependencies."""
    pyproject_path = os.path.join(ROOT_DIR, "growthscout-python", "pyproject.toml")
    assert os.path.exists(pyproject_path)
    with open(pyproject_path, "r") as f:
        content = f.read()

    assert "[tool.poetry]" in content
    assert "poetry-core" in content
    assert "httpx" in content
    assert "pydantic" in content
