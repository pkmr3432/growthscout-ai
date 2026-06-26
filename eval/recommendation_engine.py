#!/usr/bin/env python3
"""
GrowthScout AI — Structured Recommendation Engine
Converts evaluation failures and gate breaches into canonical structured JSON recommendations
and renders user-friendly Markdown summaries.
"""

import os
import sys
import json
import yaml
import glob
from pathlib import Path

def get_latest_results(results_dir):
    files = glob.glob(str(Path(results_dir) / "results_*.json"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def generate_recommendations(candidate_path, manifest_path):
    with open(candidate_path) as f:
        candidate_data = json.load(f)
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f)
        
    cases = candidate_data.get("eval_cases", []) or candidate_data.get("test_cases", [])
    
    # Calculate metric averages
    totals = {}
    counts = {}
    for case in cases:
        grades = case.get("grades", {}) or case.get("metrics", {})
        for metric, info in grades.items():
            score = info.get("score") if isinstance(info, dict) else info
            if score is not None:
                totals[metric] = totals.get(metric, 0.0) + float(score)
                counts[metric] = counts.get(metric, 0) + 1
                
    averages = {m: totals[m] / counts[m] for m in totals}
    
    recommendations_list = []
    
    # Check deterministic metrics thresholds
    det_config = manifest.get("metrics", {}).get("deterministic", {})
    for metric_name, cfg in det_config.items():
        threshold = cfg.get("threshold", 1.0)
        cand_score = averages.get(metric_name, 0.0)
        
        if cand_score < threshold:
            failing_cases = []
            for case in cases:
                grades = case.get("grades", {}) or case.get("metrics", {})
                info = grades.get(metric_name, {})
                score = info.get("score") if isinstance(info, dict) else info
                if score is not None and score < threshold:
                    failing_cases.append(case.get("eval_case_id") or case.get("case_id") or "unknown")
                    
            rec = {
                "metric": metric_name,
                "severity": cfg.get("severity", "high"),
                "root_cause": f"Average score {cand_score:.2f} fell below deterministic threshold {threshold:.2f}.",
                "confidence": 0.95,
                "failing_cases": failing_cases,
                "recommendations": [
                    f"Validate that Opportunity lead score heuristics match criteria (+35 for booking, +30 for mobile, +15 for schema, +10 for GA).",
                    f"Check that all tool invocation outputs return structurally valid types and conform to Pydantic schemas.",
                    f"Verify that workflow orchestrator handles state transitions correctly in the failing cases: {', '.join(failing_cases[:3])}."
                ]
            }
            recommendations_list.append(rec)
            
    # Check probabilistic metrics thresholds
    prob_config = manifest.get("metrics", {}).get("probabilistic", {})
    for metric_name, cfg in prob_config.items():
        threshold = cfg.get("threshold", 0.80)
        cand_score = averages.get(metric_name, 0.0)
        
        if cand_score < threshold:
            failing_cases = []
            for case in cases:
                grades = case.get("grades", {}) or case.get("metrics", {})
                info = grades.get(metric_name, {})
                score = info.get("score") if isinstance(info, dict) else info
                if score is not None and score < threshold:
                    failing_cases.append(case.get("eval_case_id") or case.get("case_id") or "unknown")
                    
            rec = {
                "metric": metric_name,
                "severity": cfg.get("severity", "medium"),
                "root_cause": f"Average LLM-as-a-judge score {cand_score:.2f} is below target threshold {threshold:.2f}.",
                "confidence": 0.85,
                "failing_cases": failing_cases,
                "recommendations": [
                    f"Improve factual grounding and citation mapping (ensure aud_ and opp_ ID prefixes are correctly injected).",
                    f"Adjust prompt template inside orchestrator_agent to encourage consulting depth and plain business owner language.",
                    f"Ensure recommendations outline concrete, step-by-step action items for SMB owners."
                ]
            }
            # Custom recommendations by metric name
            if metric_name == "consultant_confidence_score":
                rec["recommendations"] = [
                    "Verify consulting report markdown headers flow logically from Audit to Opportunity Scoring.",
                    "Review report spelling and grammar; avoid generic placeholder phrases or overly dry technical terminology.",
                    "Ensure report includes clear priority ratings so that the client can confidently execute recommendations."
                ]
            recommendations_list.append(rec)
            
    # If everything passed, create a default "maintain" recommendation
    if not recommendations_list:
        recommendations_list.append({
            "metric": "all_metrics",
            "severity": "low",
            "root_cause": "All quality gates successfully passed. Quality matches baseline.",
            "confidence": 1.0,
            "failing_cases": [],
            "recommendations": [
                "Maintain current prompt structures and configurations.",
                "Continue monitoring nightly cron evaluation runs for long-term drift."
            ]
        })
        
    return recommendations_list

def render_markdown(recs):
    md = []
    md.append("## 💡 Actionable Quality Recommendations")
    for r in recs:
        icon = "❌" if r["severity"] in ["critical", "high"] else "⚠️"
        if r["metric"] == "all_metrics":
            icon = "✅"
        md.append(f"\n### {icon} Metric: `{r['metric']}` (Severity: **{r['severity'].upper()}**)")
        md.append(f"*   **Root Cause**: {r['root_cause']}")
        md.append(f"*   **Confidence Rating**: {r['confidence'] * 100:.0f}%")
        if r["failing_cases"]:
            md.append(f"*   **Failing Cases**: {', '.join(r['failing_cases'][:10])}")
        md.append("*   **Action Items**:")
        for step in r["recommendations"]:
            md.append(f"    - {step}")
    return "\n".join(md)

def main():
    workspace_root = Path(__file__).resolve().parents[1]
    
    # Paths
    results_dir = workspace_root / "artifacts" / "grade_results"
    candidate_path = get_latest_results(results_dir)
    
    if not candidate_path:
        candidate_path = workspace_root / "eval" / "baselines" / "mock_candidate_results.json"
        
    manifest_path = workspace_root / "eval" / "quality_manifest.yaml"
    
    recs = generate_recommendations(candidate_path, manifest_path)
    
    # Save canonical structured JSON output
    history_dir = workspace_root / "artifacts" / "evaluation_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    
    json_out = history_dir / "recommendations.json"
    with open(json_out, "w") as f:
        json.dump(recs, f, indent=2)
    print(f"Saved structured JSON recommendations to: {json_out}")
    
    # Render and save Markdown report
    md_out = history_dir / "recommendations.md"
    md_content = render_markdown(recs)
    with open(md_out, "w") as f:
        f.write(md_content)
    print(f"Saved Markdown recommendations report to: {md_out}")

if __name__ == "__main__":
    main()
