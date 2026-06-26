import os
import json
import glob
from pathlib import Path
from datetime import datetime, timezone
import subprocess

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "local_dev"

def generate_trend_report():
    workspace_root = Path(__file__).resolve().parents[1]
    
    # 1. Determine evaluation history directory based on environment variable or default
    history_dir_env = os.environ.get("GROWTHSCOUT_EVAL_HISTORY_DIR")
    if history_dir_env:
        history_dir = Path(history_dir_env)
    else:
        history_dir = workspace_root / "artifacts" / "evaluation_history"
        
    history_dir.mkdir(parents=True, exist_ok=True)
    history_file = history_dir / "quality_history.json"
    
    # 2. Locate the latest results JSON file in artifacts/grade_results/
    results_dir = workspace_root / "artifacts" / "grade_results"
    results_files = glob.glob(str(results_dir / "results_*.json"))
    
    if not results_files:
        print("No evaluation results files found in artifacts/grade_results/. Skipping trend logging.")
        return
        
    latest_results_file = max(results_files, key=os.path.getmtime)
    print(f"Parsing latest evaluation results: {latest_results_file}")
    
    with open(latest_results_file, "r") as f:
        results_data = json.load(f)
        
    # We parse cases and calculate averages for each metric
    cases = results_data.get("eval_cases", [])
    if not cases:
        cases = results_data.get("test_cases", [])
        
    if not cases:
        print("No cases found in the results file.")
        return
        
    metric_totals = {}
    metric_counts = {}
    
    for case in cases:
        # Check if it has grades/scores
        grades = case.get("grades", {}) or case.get("metrics", {})
        # If it's stored under a different nested format:
        if not grades and "evaluation_results" in case:
            grades = case["evaluation_results"]
            
        for metric_name, metric_info in grades.items():
            score = None
            if isinstance(metric_info, dict):
                score = metric_info.get("score")
            elif isinstance(metric_info, (int, float)):
                score = metric_info
                
            if score is not None:
                metric_totals[metric_name] = metric_totals.get(metric_name, 0.0) + float(score)
                metric_counts[metric_name] = metric_counts.get(metric_name, 0) + 1
                
    averages = {}
    for metric_name in metric_totals:
        averages[metric_name] = round(metric_totals[metric_name] / metric_counts[metric_name], 3)
        
    # 3. Load existing history or initialize
    if history_file.exists():
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception:
            history = []
    else:
        history = []
        
    # 4. Append new entry
    new_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit_hash": get_git_commit(),
        "results_source": Path(latest_results_file).name,
        "metrics": averages
    }
    
    history.append(new_entry)
    
    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)
        
    print(f"Successfully appended trend record to {history_file}:")
    print(json.dumps(new_entry, indent=2))

if __name__ == "__main__":
    generate_trend_report()
