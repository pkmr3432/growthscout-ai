#!/usr/bin/env python3
"""
GrowthScout AI — CI Report Generator
Generates GitHub Step Summary (Markdown), HTML Dashboard, and machine-readable final JSON reports.
Embeds comprehensive evaluation metadata in every report.
"""

import os
import sys
import json
import yaml
import argparse
import subprocess
from datetime import datetime, timezone
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="GrowthScout AI CI Report Generator")
    parser.add_argument("--candidate", type=str, help="Path to candidate results JSON file")
    parser.add_argument("--pipeline", type=str, default="fast_ci", choices=["fast_ci", "full_eval"],
                        help="Pipeline type context")
    return parser.parse_args()

def load_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def get_git_commit():
    try:
        res = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return "local_dev"

def get_latest_results(results_dir):
    import glob
    files = glob.glob(str(Path(results_dir) / "results_*.json"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def main():
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]
    
    # 1. Load Quality Manifest
    manifest_path = workspace_root / "eval" / "quality_manifest.yaml"
    if not manifest_path.exists():
        print(f"Error: Quality manifest not found at {manifest_path}")
        sys.exit(1)
    manifest = load_yaml(manifest_path)
    
    # 2. Collect Metadata
    manifest_meta = manifest.get("metadata", {})
    git_commit = get_git_commit()
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    evaluation_metadata = {
        "evaluation_version": manifest_meta.get("evaluation_version", "1.3.0"),
        "dataset_version": manifest.get("dataset_versions", {}).get("discovery", "1.1.0"),
        "prompt_version": manifest_meta.get("prompt_version", "2.4.0"),
        "model_version": manifest_meta.get("model_version", "gemini-1.5-pro-002"),
        "provider": manifest_meta.get("provider", "google"),
        "model_revision": manifest_meta.get("model_revision", "2024-09-02"),
        "temperature": manifest_meta.get("temperature", 0.0),
        "commit_hash": git_commit,
        "timestamp": timestamp,
        "pipeline_type": "fast_ci" if args.pipeline == "fast_ci" else "full_evaluation"
    }
    
    # 3. Locate gate results & candidate results
    history_dir_env = os.environ.get("GROWTHSCOUT_EVAL_HISTORY_DIR")
    if history_dir_env:
        history_dir = Path(history_dir_env)
    else:
        history_dir = workspace_root / "artifacts" / "evaluation_history"
    
    gate_results_path = history_dir / "ci_gate_results.json"
    if not gate_results_path.exists():
        print(f"Warning: Gate results file not found at {gate_results_path}. Run compare_ci_regression.py first.")
        gate_data = {
            "build_failed": False,
            "has_deterministic_failures": False,
            "has_probabilistic_failures": False,
            "gate_results": []
        }
    else:
        gate_data = load_json(gate_results_path)
        
    candidate_path = args.candidate
    if not candidate_path:
        results_dir = workspace_root / "artifacts" / "grade_results"
        candidate_path = get_latest_results(results_dir)
        
    candidate_averages = {}
    if candidate_path and Path(candidate_path).exists():
        cand_raw = load_json(candidate_path)
        # Parse averages
        from compare_ci_regression import calculate_averages
        candidate_averages = calculate_averages(cand_raw)
        
    # 4. Generate Combined JSON Report
    final_report = {
        "evaluation_metadata": evaluation_metadata,
        "gate_status": {
            "build_failed": gate_data.get("build_failed", False),
            "has_deterministic_failures": gate_data.get("has_deterministic_failures", False),
            "has_probabilistic_failures": gate_data.get("has_probabilistic_failures", False)
        },
        "metrics_averages": candidate_averages,
        "detailed_gate_results": gate_data.get("gate_results", [])
    }
    
    final_report_path = history_dir / "final_ci_report.json"
    with open(final_report_path, "w") as f:
        json.dump(final_report, f, indent=2)
    print(f"Generated final JSON report at: {final_report_path}")
    
    # 5. Generate Markdown Summary (GitHub Step Summary)
    md_lines = []
    md_lines.append("# 🚀 GrowthScout AI — Evaluation Pipeline Summary")
    md_lines.append(f"\n**Pipeline Run Status:** {'❌ FAILED' if final_report['gate_status']['build_failed'] else '✅ PASSED'}")
    md_lines.append(f"\n### 📊 Metadata")
    md_lines.append(f"| Property | Value |")
    md_lines.append(f"| :--- | :--- |")
    for k, v in evaluation_metadata.items():
        md_lines.append(f"| `{k}` | `{v}` |")
        
    md_lines.append(f"\n### 🔬 Quality Gate Results")
    md_lines.append(f"| Metric | Type | Candidate | Baseline | Threshold | Status | Review Policy |")
    md_lines.append(f"| :--- | :--- | :---: | :---: | :---: | :---: | :--- |")
    for gate in final_report["detailed_gate_results"]:
        status_icon = "✅" if "PASS" in gate["status"] else ("⚠️" if gate["status"] == "WARN" else "❌")
        md_lines.append(f"| `{gate['metric']}` | {gate['type']} | `{gate['candidate_score']:.4f}` | `{gate['baseline_score']:.4f}` | `{gate['threshold']:.2f}` | {status_icon} {gate['status']} | `{gate['policy_triggered']}` |")
        
    # Write warnings or policy notes
    has_warnings = False
    for gate in final_report["detailed_gate_results"]:
        if gate.get("policy_log"):
            if not has_warnings:
                md_lines.append(f"\n### ⚠️ Policy Notes")
                has_warnings = True
            md_lines.append(f"*   **{gate['metric']}**: {gate['policy_log']}")
            
    md_summary = "\n".join(md_lines)
    
    # Write to GITHUB_STEP_SUMMARY if available
    summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_env:
        with open(summary_env, "w") as f:
            f.write(md_summary)
        print(f"Written Step Summary to GITHUB_STEP_SUMMARY")
    else:
        summary_path = history_dir / "github_step_summary.md"
        with open(summary_path, "w") as f:
            f.write(md_summary)
        print(f"Generated Markdown Summary at: {summary_path}")
        
    # 6. Generate HTML Dashboard
    html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>GrowthScout AI — Quality Gates Dashboard</title>
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            margin: 0;
            padding: 40px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: #1e293b;
            border-radius: 12px;
            box-shadow: 0 10px 15px -3px rgba(0,0,0,0.5);
            padding: 30px;
            border: 1px solid #334155;
        }}
        h1 {{
            color: #f8fafc;
            margin-top: 0;
            font-size: 28px;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
        }}
        h2 {{
            color: #38bdf8;
            font-size: 20px;
            margin-top: 30px;
            margin-bottom: 15px;
        }}
        .badge {{
            padding: 8px 16px;
            border-radius: 9999px;
            font-weight: bold;
            display: inline-block;
            margin-bottom: 20px;
        }}
        .badge-pass {{
            background-color: #065f46;
            color: #34d399;
        }}
        .badge-fail {{
            background-color: #991b1b;
            color: #f87171;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background-color: #0f172a;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #334155;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background-color: #0f172a;
            color: #94a3b8;
        }}
        tr:hover {{
            background-color: #334155;
        }}
        .pass {{ color: #34d399; font-weight: bold; }}
        .fail {{ color: #f87171; font-weight: bold; }}
        .warn {{ color: #fbbf24; font-weight: bold; }}
        .policy-log {{
            background-color: #0f172a;
            border-left: 4px solid #fbbf24;
            padding: 10px;
            margin-top: 10px;
            border-radius: 0 4px 4px 0;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 GrowthScout AI — Quality Gates Dashboard</h1>
        
        <div class="badge {status_class}">
            Pipeline Run Status: {status_text}
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>📊 Metadata</h2>
                <table>
                    {metadata_table_rows}
                </table>
            </div>
            <div class="card">
                <h2>📈 Gate Verification Summary</h2>
                <table>
                    <tr><th>Deterministic Failures</th><td class="{det_class}">{det_text}</td></tr>
                    <tr><th>Probabilistic Failures</th><td class="{prob_class}">{prob_text}</td></tr>
                    <tr><th>Active Pipeline</th><td><code>{pipeline_type}</code></td></tr>
                </table>
            </div>
        </div>
        
        <h2>🔬 Detailed Quality Gate Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Type</th>
                    <th>Candidate Score</th>
                    <th>Baseline Score</th>
                    <th>Threshold</th>
                    <th>Status</th>
                    <th>Review Policy</th>
                </tr>
            </thead>
            <tbody>
                {results_table_rows}
            </tbody>
        </table>
        
        {policy_notes_section}
    </div>
</body>
</html>
"""
    status_class = "badge-fail" if final_report["gate_status"]["build_failed"] else "badge-pass"
    status_text = "FAILED" if final_report["gate_status"]["build_failed"] else "PASSED"
    
    det_class = "fail" if final_report["gate_status"]["has_deterministic_failures"] else "pass"
    det_text = "YES (Blocked)" if final_report["gate_status"]["has_deterministic_failures"] else "NONE"
    
    prob_class = "warn" if final_report["gate_status"]["has_probabilistic_failures"] else "pass"
    prob_text = "YES (Triggered Policy)" if final_report["gate_status"]["has_probabilistic_failures"] else "NONE"
    
    # Metadata rows
    metadata_rows = []
    for k, v in evaluation_metadata.items():
        metadata_rows.append(f"<tr><th>{k}</th><td><code>{v}</code></td></tr>")
    metadata_table_rows = "\n".join(metadata_rows)
    
    # Results rows
    results_rows = []
    for gate in final_report["detailed_gate_results"]:
        status_label = gate["status"]
        if "PASS" in status_label:
            cls = "pass"
        elif status_label == "WARN":
            cls = "warn"
        else:
            cls = "fail"
            
        results_rows.append(f"""
        <tr>
            <td><code>{gate['metric']}</code></td>
            <td>{gate['type']}</td>
            <td><code>{gate['candidate_score']:.4f}</code></td>
            <td><code>{gate['baseline_score']:.4f}</code></td>
            <td><code>{gate['threshold']:.2f}</code></td>
            <td class="{cls}">{status_label}</td>
            <td><code>{gate['policy_triggered']}</code></td>
        </tr>
        """)
    results_table_rows = "\n".join(results_rows)
    
    # Policy notes section
    policy_notes_rows = []
    for gate in final_report["detailed_gate_results"]:
        if gate.get("policy_log"):
            policy_notes_rows.append(f"""
            <div class="policy-log">
                <strong>{gate['metric']}</strong>: {gate['policy_log']}
            </div>
            """)
            
    policy_notes_section = ""
    if policy_notes_rows:
        policy_notes_section = "<h2>⚠️ Review Policy Logs</h2>" + "\n".join(policy_notes_rows)
        
    html_content = html_template.format(
        status_class=status_class,
        status_text=status_text,
        metadata_table_rows=metadata_table_rows,
        det_class=det_class,
        det_text=det_text,
        prob_class=prob_class,
        prob_text=prob_text,
        pipeline_type=evaluation_metadata["pipeline_type"],
        results_table_rows=results_table_rows,
        policy_notes_section=policy_notes_section
    )
    
    html_dashboard_path = history_dir / "results_dashboard.html"
    with open(html_dashboard_path, "w") as f:
        f.write(html_content)
    print(f"Generated HTML dashboard at: {html_dashboard_path}")

if __name__ == "__main__":
    main()
