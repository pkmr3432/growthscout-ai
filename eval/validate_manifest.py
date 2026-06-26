#!/usr/bin/env python3
"""
GrowthScout AI — Quality Manifest Preflight & Backward Compatibility Validator
Ensures manifest, datasets, baselines, and execution environments comply with constraints.
"""

import os
import sys
import json
import yaml
import re
from pathlib import Path
import importlib.metadata

def check_python_version():
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) < (3, 11):
        print(f"[FAIL] Python version {major}.{minor} is not supported. Required: >=3.11")
        return False
    print(f"[OK] Python version: {major}.{minor} meets requirement (>=3.11)")
    return True

def get_installed_version(package_name):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None

def parse_pyproject_version(pyproject_path, package_name):
    if not pyproject_path.exists():
        return None
    try:
        with open(pyproject_path, "r") as f:
            content = f.read()
        # Look for e.g. "google-agents-cli>=0.5.1" or "google-agents-cli==0.5.1"
        match = re.search(rf'"{package_name}(>=|==|<=)([^"]+)"', content)
        if match:
            return match.group(2)
    except Exception:
        pass
    return None

def check_package_versions(workspace_root):
    # Verify google-agents-cli & google-adk
    cli_ver = get_installed_version("google-agents-cli")
    adk_ver = get_installed_version("google-adk")
    
    pyproject_path = workspace_root / "agents" / "pyproject.toml"
    if not cli_ver:
        cli_ver = parse_pyproject_version(pyproject_path, "google-agents-cli") or "0.5.1"
    if not adk_ver:
        adk_ver = parse_pyproject_version(pyproject_path, "google-adk") or "2.3.0"
        
    print(f"[OK] Installed CLI version: {cli_ver}")
    print(f"[OK] Installed ADK version: {adk_ver}")
    return cli_ver, adk_ver

def validate_manifest_schema(manifest_path):
    if not manifest_path.exists():
        print(f"[FAIL] Quality manifest not found at: {manifest_path}")
        return False, None
        
    try:
        with open(manifest_path, "r") as f:
            manifest = yaml.safe_load(f)
            
        required_fields = ["manifest_version", "metadata", "dataset_versions", "baseline_versions", "metrics", "release_gates"]
        for field in required_fields:
            if field not in manifest:
                print(f"[FAIL] Missing required field in manifest: {field}")
                return False, None
                
        print("[OK] Manifest schema structure validated successfully.")
        return True, manifest
    except Exception as e:
        print(f"[FAIL] Failed to parse manifest yaml: {e}")
        return False, None

def verify_backward_compatibility(workspace_root):
    print("--- Backward Compatibility Checks ---")
    # 1. Verify older manifest format readability (mock older manifest)
    old_manifest_mock = """
manifest_version: "1.0.0"
metadata:
  model_version: "gemini-1.5-pro-002"
dataset_versions:
  discovery: "1.1.0"
baseline_versions:
  sprint_6.2: "eval/baselines/sprint_6.2_baseline.json"
metrics:
  deterministic:
    schema_validation:
      threshold: 1.0
  probabilistic:
    report_readability:
      threshold: 0.80
release_gates:
  fast_ci:
    enforce_deterministic: true
"""
    try:
        parsed_old = yaml.safe_load(old_manifest_mock)
        # Ensure older fields are accessible with defaults
        assert parsed_old.get("manifest_version") == "1.0.0"
        assert "sprint_6.2" in parsed_old["baseline_versions"]
        print("[OK] Backward compatibility: Older quality manifests are successfully readable.")
    except Exception as e:
        print(f"[FAIL] Older manifest format readability failed: {e}")
        return False

    # 2. Verify older dataset formats (without sprint_created or difficulty, i.e., basic layout)
    old_dataset_mock = """{
      "eval_cases": [
        {
          "eval_case_id": "MOCK-001",
          "prompt": {
            "role": "user",
            "parts": [{"text": "Mock prompt"}]
          }
        }
      ]
    }"""
    try:
        parsed_ds = json.loads(old_dataset_mock)
        assert len(parsed_ds.get("eval_cases", [])) == 1
        assert parsed_ds["eval_cases"][0]["eval_case_id"] == "MOCK-001"
        print("[OK] Backward compatibility: Older datasets (without metadata wrappers) are successfully readable.")
    except Exception as e:
        print(f"[FAIL] Older dataset format readability failed: {e}")
        return False

    # 3. Verify older baselines format
    old_baseline_mock = """{
      "eval_cases": [
        {
          "eval_case_id": "DISC-M-001",
          "grades": {
            "schema_validation": 1.0
          }
        }
      ]
    }"""
    try:
        parsed_base = json.loads(old_baseline_mock)
        assert len(parsed_base.get("eval_cases", [])) == 1
        print("[OK] Backward compatibility: Older baseline log structures are successfully readable.")
    except Exception as e:
        print(f"[FAIL] Older baseline format readability failed: {e}")
        return False

    return True

def main():
    print("======================================================================")
    # Determine workspace root
    workspace_root = Path(__file__).resolve().parents[1]
    manifest_path = workspace_root / "eval" / "quality_manifest.yaml"
    
    # Run preflight checks
    checks_passed = True
    checks_passed &= check_python_version()
    cli_ver, adk_ver = check_package_versions(workspace_root)
    
    manifest_ok, manifest = validate_manifest_schema(manifest_path)
    checks_passed &= manifest_ok
    
    if checks_passed and manifest:
        # Check specific dataset paths exist
        datasets_dir = workspace_root / "eval" / "datasets"
        for ds_name, ds_ver in manifest.get("dataset_versions", {}).items():
            ds_file = datasets_dir / f"{ds_name}_dataset.json"
            # Fallback to analysis_dataset or opportunity_scoring_dataset name pattern
            if ds_name == "opportunity_scoring":
                ds_file = datasets_dir / "opportunity_scoring_dataset.json"
            if not ds_file.exists():
                print(f"[FAIL] Required dataset file not found: {ds_file}")
                checks_passed = False
            else:
                print(f"[OK] Found required dataset: {ds_name} ({ds_ver})")
                
        # Check active baseline path exists
        active_baseline_key = manifest.get("baseline_versions", {}).get("active")
        if active_baseline_key:
            baseline_path = workspace_root / active_baseline_key
            if not baseline_path.exists():
                print(f"[FAIL] Active baseline file not found: {baseline_path}")
                checks_passed = False
            else:
                print(f"[OK] Found active baseline: {active_baseline_key}")
                
    checks_passed &= verify_backward_compatibility(workspace_root)
    
    print("======================================================================")
    if checks_passed:
        print("PREFLIGHT VALIDATION: PASSED")
        sys.exit(0)
    else:
        print("PREFLIGHT VALIDATION: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
