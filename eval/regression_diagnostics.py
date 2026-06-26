#!/usr/bin/env python3
"""
GrowthScout AI — Regression Diagnostic & Correlation Engine
Categorizes regressions based on git differences, file modifications, and metric comparisons.
"""

import os
import sys
import json
import yaml
import subprocess
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="GrowthScout AI Regression Diagnostics")
    parser.add_argument("--candidate", type=str, help="Path to candidate results JSON")
    parser.add_argument("--baseline", type=str, help="Path to baseline results JSON")
    parser.add_argument("--mock-failure", action="store_true", help="Simulate a diagnostic regression run")
    return parser.parse_args()

def get_git_diff_files():
    try:
        # Get list of files modified or staged
        res = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        files = []
        for line in res.stdout.splitlines():
            if line.strip():
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    files.append(parts[1])
        return files
    except Exception:
        return []

def classify_changes(modified_files):
    categories = set()
    for file in modified_files:
        if "pyproject.toml" in file or "uv.lock" in file or "requirements" in file:
            categories.add("Dependency Regression")
        elif "quality_manifest.yaml" in file or "eval_config.yaml" in file:
            categories.add("Configuration Regression")
        elif "eval/datasets/" in file:
            categories.add("Dataset Regression")
        elif "eval/" in file and ("compare" in file or "generate" in file or "test" in file):
            categories.add("Evaluation Regression")
        elif "agents/" in file and "agent.py" in file:
            categories.add("Prompt Regression")
        elif "mcp/" in file or "servers/" in file:
            categories.add("Tool Regression")
        elif "utils/schema_integration" in file or "models.py" in file:
            categories.add("Schema Regression")
        elif ".github/" in file or "Dockerfile" in file or "terraform" in file:
            categories.add("Infrastructure Regression")
            
    if not categories:
        categories.add("Model Regression") # Default to external model changes if no files changed
    return list(categories)

def perform_diagnostics(candidate_data, baseline_data, mock=False):
    print("--- RUNNING REGRESSION DIAGNOSTICS ---")
    regressions = []
    
    cand_cases = {c["eval_case_id"]: c for c in candidate_data.get("eval_cases", [])}
    base_cases = {c["eval_case_id"]: c for c in baseline_data.get("eval_cases", [])}
    
    for case_id, cand_case in cand_cases.items():
        if case_id not in base_cases:
            continue
        base_case = base_cases[case_id]
        
        cand_grades = cand_case.get("grades", {})
        base_grades = base_case.get("grades", {})
        
        for metric, cand_info in cand_grades.items():
            if metric not in base_grades:
                continue
            base_info = base_grades[metric]
            
            c_score = cand_info.get("score", 0.0) if isinstance(cand_info, dict) else cand_info
            b_score = base_info.get("score", 0.0) if isinstance(base_info, dict) else base_info
            
            if c_score < b_score:
                regressions.append({
                    "case_id": case_id,
                    "metric": metric,
                    "candidate_score": c_score,
                    "baseline_score": b_score,
                    "delta": round(c_score - b_score, 4)
                })
                
    modified_files = get_git_diff_files()
    if mock:
        modified_files = ["agents/orchestrator_agent/agent.py", "eval/datasets/discovery_dataset.json"]
        regressions.append({
            "case_id": "DISC-M-001",
            "metric": "consultant_confidence_score",
            "candidate_score": 0.75,
            "baseline_score": 0.80,
            "delta": -0.05
        })
        
    change_types = classify_changes(modified_files)
    
    diagnostics_report = {
        "has_regressions": len(regressions) > 0,
        "regressions_count": len(regressions),
        "regressions": regressions,
        "modified_files": modified_files,
        "classified_regression_categories": change_types,
        "diagnostic_summary": f"Detected {len(regressions)} regressions correlated with modifications in: {', '.join(change_types)}."
    }
    
    print(f"Diagnostics: {diagnostics_report['diagnostic_summary']}")
    for reg in regressions:
         print(f"  [REGRESSION] Case={reg['case_id']}, Metric={reg['metric']}, Drop={reg['delta']:.2f}")
         
    return diagnostics_report

def main():
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]
    
    if args.mock_failure:
        # Simulate loading results
        mock_candidate = {
            "eval_cases": [
                {
                    "eval_case_id": "DISC-M-001",
                    "grades": {
                        "consultant_confidence_score": 0.75,
                        "schema_validation": 1.0
                    }
                }
            ]
        }
        mock_baseline = {
            "eval_cases": [
                {
                    "eval_case_id": "DISC-M-001",
                    "grades": {
                        "consultant_confidence_score": 0.80,
                        "schema_validation": 1.0
                    }
                }
            ]
        }
        report = perform_diagnostics(mock_candidate, mock_baseline, mock=True)
        # Save output
        history_dir = workspace_root / "artifacts" / "evaluation_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        with open(history_dir / "regression_diagnostics.json", "w") as f:
            json.dump(report, f, indent=2)
        print(f"Saved mock diagnostics to {history_dir / 'regression_diagnostics.json'}")
        sys.exit(0)
        
    # Standard check
    candidate_path = args.candidate
    baseline_path = args.baseline
    
    if not candidate_path or not baseline_path:
        # Search latest candidate
        import glob
        results_dir = workspace_root / "artifacts" / "grade_results"
        candidate_files = glob.glob(str(results_dir / "results_*.json"))
        if not candidate_files:
            print("Error: No candidate files found.")
            sys.exit(0)
        candidate_path = max(candidate_files, key=os.path.getmtime)
        
        # Manifest
        manifest_path = workspace_root / "eval" / "quality_manifest.yaml"
        if manifest_path.exists():
            with open(manifest_path, "r") as f:
                manifest = yaml.safe_load(f)
            baseline_path = workspace_root / manifest.get("baseline_versions", {}).get("active", "eval/baselines/sprint_6.2_baseline.json")
            
    if not Path(candidate_path).exists() or not Path(baseline_path).exists():
        print("Missing candidate or baseline file for diagnostics.")
        sys.exit(0)
        
    with open(candidate_path) as f:
        cand_data = json.load(f)
    with open(baseline_path) as f:
        base_data = json.load(f)
        
    report = perform_diagnostics(cand_data, base_data)
    history_dir = workspace_root / "artifacts" / "evaluation_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    with open(history_dir / "regression_diagnostics.json", "w") as f:
        json.dump(report, f, indent=2)
    print(f"Saved diagnostics to {history_dir / 'regression_diagnostics.json'}")

if __name__ == "__main__":
    main()
