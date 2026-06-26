import json
from pathlib import Path
from collections import Counter

DATASETS = [
    ("Discovery Dataset", "discovery_dataset.json", "eval_cases"),
    ("Website Analysis Dataset", "analysis_dataset.json", "eval_cases"),
    ("Recommendation Dataset", "recommendation_dataset.json", "eval_cases"),
    ("Competitor Dataset", "competitor_dataset.json", "test_cases"),
    ("Opportunity Scoring Dataset", "opportunity_scoring_dataset.json", "test_cases")
]

DATASETS_DIR = Path(__file__).resolve().parent / "datasets"

def generate_report():
    total_cases = 0
    all_business_types = Counter()
    all_geographies = Counter()
    all_difficulties = Counter()
    all_categories = Counter()
    all_sources = Counter()
    all_sprints = Counter()
    all_edge_cases = Counter()
    
    dataset_details = []
    
    for label, filename, cases_key in DATASETS:
        file_path = DATASETS_DIR / filename
        if not file_path.exists():
            print(f"Warning: {filename} does not exist.")
            continue
            
        with open(file_path, "r") as f:
            data = json.load(f)
            
        ds_metadata = data.get("metadata", {})
        cases = data.get(cases_key, [])
        ds_case_count = len(cases)
        total_cases += ds_case_count
        
        # Track dataset-level metadata
        dataset_details.append({
            "label": label,
            "filename": filename,
            "version": ds_metadata.get("dataset_version", "N/A"),
            "schema_version": ds_metadata.get("schema_version", "N/A"),
            "generated_in": ds_metadata.get("generated_in", "N/A"),
            "last_reviewed": ds_metadata.get("last_reviewed", "N/A"),
            "maintainer": ds_metadata.get("maintainer", "N/A"),
            "count": ds_case_count
        })
        
        for case in cases:
            meta = case.get("metadata", {})
            if not meta:
                continue
                
            all_business_types[meta.get("business_type", "unknown")] += 1
            all_difficulties[meta.get("difficulty", "unknown")] += 1
            all_categories[meta.get("category", "unknown")] += 1
            all_sources[meta.get("source", "unknown")] += 1
            all_sprints[meta.get("sprint_created", "unknown")] += 1
            
            # Extract geo from tags
            geo_tag = next((tag for tag in meta.get("tags", []) if tag in [
                "austin", "seattle", "chicago", "miami", "boston", "denver", "portland", "atlanta", "dallas", "san_diego", 
                "phoenix", "philadelphia", "houston", "orlando", "nashville", "las_vegas", "minneapolis", "san_jose", 
                "charlotte", "detroit", "salt_lake_city", "st._louis", "tampa"
            ]), "global/other")
            all_geographies[geo_tag.replace("_", " ").title()] += 1
            
            # Extract edge-case types from tags/edge_case_type
            if "edge_case_type" in case:
                all_edge_cases[case["edge_case_type"]] += 1
            else:
                # Infer from tags
                for tag in meta.get("tags", []):
                    if tag in ["robots_txt", "network_error", "limit_constraint"]:
                        all_edge_cases[tag] += 1
                        
    # Build report Markdown string
    md = []
    md.append("# GrowthScout AI — Evaluation Dataset Coverage Report")
    md.append(f"\nThis report is automatically generated to document coverage statistics, diversity metrics, and edge-case distributions across all golden evaluation datasets.")
    
    md.append("\n## 1. Golden Dataset Inventory")
    md.append("| Dataset | File | Cases | Dataset Version | Schema Version | Last Reviewed | Maintainer |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for ds in dataset_details:
        md.append(f"| **{ds['label']}** | `{ds['filename']}` | {ds['count']} | {ds['version']} | {ds['schema_version']} | {ds['last_reviewed']} | {ds['maintainer']} |")
    md.append(f"| **Total Summary** | - | **{total_cases}** | - | - | - | - |")
    
    md.append("\n## 2. Business Type (Industry) Diversity")
    md.append("| Business Type (Niche) | Case Count | Percentage |")
    md.append("| :--- | :--- | :--- |")
    for biz, count in all_business_types.most_common():
        pct = (count / total_cases) * 100
        md.append(f"| `{biz}` | {count} | {pct:.1f}% |")
        
    md.append("\n## 3. Geographic Diversity")
    md.append("| City / Market | Case Count | Percentage |")
    md.append("| :--- | :--- | :--- |")
    for geo, count in all_geographies.most_common():
        pct = (count / total_cases) * 100
        md.append(f"| {geo} | {count} | {pct:.1f}% |")
        
    md.append("\n## 4. Difficulty Distribution")
    md.append("| Difficulty Level | Case Count | Percentage |")
    md.append("| :--- | :--- | :--- |")
    for diff, count in all_difficulties.most_common():
        pct = (count / total_cases) * 100
        md.append(f"| **{diff.title()}** | {count} | {pct:.1f}% |")
        
    md.append("\n## 5. Edge-Case & Scenario Distribution")
    md.append("| Edge-Case Scenario Category | Case Count |")
    md.append("| :--- | :--- |")
    for ec, count in all_edge_cases.most_common():
        md.append(f"| `{ec}` | {count} |")
        
    md.append("\n## 6. Manual vs. Synthesized Ratio")
    md.append("| Source Type | Case Count | Percentage |")
    md.append("| :--- | :--- | :--- |")
    for src, count in all_sources.most_common():
        pct = (count / total_cases) * 100
        md.append(f"| **{src.title()}** | {count} | {pct:.1f}% |")
        
    md.append("\n## 7. Dataset Growth Statistics")
    md.append("| Sprint Created | Case Count | Contribution |")
    md.append("| :--- | :--- | :--- |")
    for sprint, count in all_sprints.most_common():
        pct = (count / total_cases) * 100
        md.append(f"| `{sprint}` | {count} | {pct:.1f}% |")
        
    report_content = "\n".join(md)
    
    # Save report
    output_path = Path(__file__).resolve().parent / "coverage_report.md"
    with open(output_path, "w") as f:
        f.write(report_content)
        
    print(f"Coverage report generated successfully at: {output_path}")

if __name__ == "__main__":
    generate_report()
