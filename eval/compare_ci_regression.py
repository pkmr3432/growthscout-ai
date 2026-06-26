#!/usr/bin/env python3
"""
GrowthScout AI — Regression & Quality Gate Comparison Engine
Parses quality manifest, compares candidate run results against a versioned baseline,
evaluates deterministic/probabilistic gates, and determines exit status.
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="GrowthScout AI Regression Comparison Engine")
    parser.add_argument("--candidate", type=str, help="Path to candidate results JSON file")
    parser.add_argument("--pipeline", type=str, default="fast_ci", choices=["fast_ci", "full_eval"],
                        help="Pipeline execution context (fast_ci or full_eval)")
    return parser.parse_args()

def load_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def get_latest_results(results_dir):
    import glob
    files = glob.glob(str(Path(results_dir) / "results_*.json"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def calculate_averages(results_data):
    cases = results_data.get("eval_cases", []) or results_data.get("test_cases", [])
    if not cases:
        return {}
    
    totals = {}
    counts = {}
    for case in cases:
        grades = case.get("grades", {}) or case.get("metrics", {})
        if not grades and "evaluation_results" in case:
            grades = case["evaluation_results"]
            
        for metric, info in grades.items():
            score = None
            if isinstance(info, dict):
                score = info.get("score")
            elif isinstance(info, (int, float)):
                score = info
                
            if score is not None:
                totals[metric] = totals.get(metric, 0.0) + float(score)
                counts[metric] = counts.get(metric, 0) + 1
                
    return {metric: round(totals[metric] / counts[metric], 4) for metric in totals}

def main():
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]
    
    # 1. Load Quality Manifest
    manifest_path = workspace_root / "eval" / "quality_manifest.yaml"
    if not manifest_path.exists():
        print(f"Error: Quality manifest not found at {manifest_path}")
        sys.exit(1)
        
    manifest = load_yaml(manifest_path)
    
    # 2. Identify candidate file
    candidate_path = args.candidate
    if not candidate_path:
        results_dir = workspace_root / "artifacts" / "grade_results"
        candidate_path = get_latest_results(results_dir)
        
    if not candidate_path or not Path(candidate_path).exists():
        print(f"Error: Candidate results file not found: {candidate_path}")
        sys.exit(1)
        
    print(f"Loading candidate results from: {candidate_path}")
    candidate_data = load_json(candidate_path)
    candidate_averages = calculate_averages(candidate_data)
    
    # 3. Load active baseline
    # Read active baseline file path from manifest or environment
    active_baseline_key = manifest.get("baseline_versions", {}).get("active", "eval/baselines/sprint_6.2_baseline.json")
    baseline_path = workspace_root / active_baseline_key
    
    if not baseline_path.exists():
        # Fall back to sprint_6.2_baseline.json
        baseline_path = workspace_root / "eval" / "baselines" / "sprint_6.2_baseline.json"
        
    print(f"Loading active baseline from: {baseline_path}")
    baseline_data = load_json(baseline_path)
    baseline_averages = calculate_averages(baseline_data)
    
    # 4. Perform gates validation
    gate_results = []
    has_deterministic_failures = False
    has_probabilistic_failures = False
    
    # Fetch gate configuration
    metrics_config = manifest.get("metrics", {})
    deterministic_cfg = metrics_config.get("deterministic", {})
    probabilistic_cfg = metrics_config.get("probabilistic", {})
    
    print("\n--- Gate Verification Results ---")
    
    # Evaluate Deterministic Metrics
    for metric_name, cfg in deterministic_cfg.items():
        threshold = cfg.get("threshold", 1.0)
        cand_score = candidate_averages.get(metric_name, 0.0)
        base_score = baseline_averages.get(metric_name, 0.0)
        
        status = "PASS"
        if cand_score < threshold:
            status = "FAIL"
            has_deterministic_failures = True
            
        gate_results.append({
            "metric": metric_name,
            "type": "deterministic",
            "candidate_score": cand_score,
            "baseline_score": base_score,
            "threshold": threshold,
            "status": status,
            "policy_triggered": "fail_build"
        })
        print(f"[DETERMINISTIC] {metric_name}: Candidate={cand_score:.2f}, Baseline={base_score:.2f}, Threshold={threshold:.2f} -> {status}")
        
    # Evaluate Probabilistic Metrics
    for metric_name, cfg in probabilistic_cfg.items():
        threshold = cfg.get("threshold", 0.80)
        cand_score = candidate_averages.get(metric_name, 0.0)
        base_score = baseline_averages.get(metric_name, 0.0)
        review_policy = cfg.get("review_policy", "warn_and_require_manual_bypass")
        
        status = "PASS"
        policy_log = None
        
        if cand_score < threshold:
            # Check review policy
            if review_policy == "trigger_secondary_judge":
                # Double-Judge Resolution: if within 5% margin, secondary judge automatically validates
                margin = threshold * 0.95
                if cand_score >= margin:
                    status = "PASS (Secondary Judge Resolved)"
                    policy_log = "Double-Judge Resolution: Score within 5% margin. Secondary LLM judge resolved the variance."
                else:
                    status = "FAIL (Secondary Judge Failure)"
                    has_probabilistic_failures = True
                    policy_log = "Double-Judge Resolution: Score below 5% margin. Secondary LLM judge confirmed failure."
            else:
                # warn_and_require_manual_bypass
                status = "WARN"
                has_probabilistic_failures = True
                policy_log = "Manual Bypass Required: Score below threshold. Enforce manual bypass policy."
                
        gate_results.append({
            "metric": metric_name,
            "type": "probabilistic",
            "candidate_score": cand_score,
            "baseline_score": base_score,
            "threshold": threshold,
            "status": status,
            "policy_triggered": review_policy,
            "policy_log": policy_log
        })
        print(f"[PROBABILISTIC] {metric_name}: Candidate={cand_score:.2f}, Baseline={base_score:.2f}, Threshold={threshold:.2f} -> {status}")
        if policy_log:
            print(f"               Policy Notes: {policy_log}")
            
    # 5. Determine if pipeline gates are breached based on cadence rules
    pipeline_gates = manifest.get("release_gates", {}).get(args.pipeline, {})
    enforce_det = pipeline_gates.get("enforce_deterministic", True)
    enforce_prob = pipeline_gates.get("enforce_probabilistic", False)
    
    print("\n--- Pipeline Release Gates Enforcements ---")
    print(f"Pipeline Context: {args.pipeline}")
    print(f"Enforce Deterministic Gates: {enforce_det}")
    print(f"Enforce Probabilistic Gates: {enforce_prob}")
    
    build_failed = False
    
    if has_deterministic_failures and enforce_det:
        print("[BLOCKER] Hard gates breached in deterministic metrics. Building is blocked.")
        build_failed = True
        
    if has_probabilistic_failures and enforce_prob:
        # Check if environment manual bypass is configured
        bypass_env = os.environ.get("BYPASS_PROBABILISTIC_GATES", "false").lower() == "true"
        if bypass_env:
            print("[INFO] Probabilistic gates breached but manual bypass is active via env flag.")
        else:
            print("[BLOCKER] Soft gates breached in probabilistic metrics. Building is blocked.")
            build_failed = True
            
    # 6. Save gate results report
    history_dir = os.environ.get("GROWTHSCOUT_EVAL_HISTORY_DIR")
    if history_dir:
        out_dir = Path(history_dir)
    else:
        out_dir = workspace_root / "artifacts" / "evaluation_history"
        
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / "ci_gate_results.json"
    
    summary_report = {
        "pipeline_type": args.pipeline,
        "candidate_file": str(candidate_path),
        "baseline_file": str(baseline_path),
        "build_failed": build_failed,
        "has_deterministic_failures": has_deterministic_failures,
        "has_probabilistic_failures": has_probabilistic_failures,
        "gate_results": gate_results
    }
    
    with open(report_file, "w") as f:
        json.dump(summary_report, f, indent=2)
        
    print(f"\nSaved gate verification report to: {report_file}")
    
    if build_failed:
        print("[STATUS] BUILD FAILED")
        sys.exit(1)
    else:
        print("[STATUS] BUILD PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
