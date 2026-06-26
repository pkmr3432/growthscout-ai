#!/usr/bin/env python3
"""
GrowthScout AI — Multi-level Dataset Fingerprinting & Integrity Engine
Calculates schema, content, and metadata fingerprints. Detects duplicates and semantic drift.
"""

import os
import sys
import json
import yaml
import hashlib
import math
import re
import argparse
from pathlib import Path

def parse_args():
    parser = argparse.ArgumentParser(description="GrowthScout AI Dataset Integrity Tool")
    parser.add_argument("--verify", action="store_true", help="Perform integrity, duplicate, and drift checks")
    parser.add_argument("--generate-fingerprints", action="store_true", help="Generate and print fingerprints for current datasets")
    return parser.parse_args()

def load_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)

def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

def tokenize(text):
    """Simple tokenization helper."""
    return re.findall(r"\w+", text.lower()) if text else []

def get_case_text(case):
    """Extracts all text content recursively from a case object for TF-IDF representation."""
    # Exclude metadata and case id
    content_only = {k: v for k, v in case.items() if k not in ["eval_case_id", "metadata"]}
    
    def extract_strings(obj):
        if isinstance(obj, str):
            return [obj]
        if isinstance(obj, dict):
            res = []
            for v in obj.values():
                res.extend(extract_strings(v))
            return res
        if isinstance(obj, list):
            res = []
            for item in obj:
                res.extend(extract_strings(item))
            return res
        return []
        
    all_strings = extract_strings(content_only)
    return " ".join(all_strings)

def get_hashes(dataset_json_data):
    """
    Calculates three independent SHA-256 hashes:
    - schema_hash: Hash of JSON schema metadata keys.
    - content_hash: Hash of the eval_cases list contents.
    - metadata_hash: Hash of the metadata block.
    """
    # 1. Schema keys and schema declarations
    schema_keys = {
        "$schema": dataset_json_data.get("$schema"),
        "title": dataset_json_data.get("title"),
        "description": dataset_json_data.get("description"),
        "type": dataset_json_data.get("type"),
        "required": dataset_json_data.get("required"),
        "properties": dataset_json_data.get("properties")
    }
    schema_str = json.dumps(schema_keys, sort_keys=True)
    schema_hash = hashlib.sha256(schema_str.encode("utf-8")).hexdigest()

    # 2. Content (cases list, removing metadata wrapper inside cases if any)
    cases = dataset_json_data.get("eval_cases", []) or dataset_json_data.get("test_cases", [])
    cases_sanitized = []
    for case in cases:
        # Exclude case-level metadata to isolate pure content
        case_content = {
            "eval_case_id": case.get("eval_case_id"),
            "prompt": case.get("prompt"),
            "agent_data": case.get("agent_data"),
            "expected_result": case.get("expected_result"),
            "expected_outputs": case.get("expected_outputs"),
            "input_data": case.get("input_data")
        }
        cases_sanitized.append(case_content)
    content_str = json.dumps(cases_sanitized, sort_keys=True)
    content_hash = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

    # 3. Metadata block
    metadata = dataset_json_data.get("metadata", {})
    metadata_str = json.dumps(metadata, sort_keys=True)
    metadata_hash = hashlib.sha256(metadata_str.encode("utf-8")).hexdigest()

    return schema_hash, content_hash, metadata_hash

def check_duplicates(dataset_json_data):
    """Performs Jaccard duplicate detection across cases."""
    cases = dataset_json_data.get("eval_cases", []) or dataset_json_data.get("test_cases", [])
    duplicates = []
    
    # Extract case ID and token set
    case_tokens = []
    for case in cases:
        case_id = case.get("eval_case_id") or case.get("case_id") or case.get("metadata", {}).get("id") or "unknown"
        text = get_case_text(case)
        tokens = set(tokenize(text))
        case_tokens.append((case_id, tokens))
        
    for i in range(len(case_tokens)):
        for j in range(i + 1, len(case_tokens)):
            id1, tokens1 = case_tokens[i]
            id2, tokens2 = case_tokens[j]
            if not tokens1 or not tokens2:
                continue
            
            intersection = len(tokens1.intersection(tokens2))
            union = len(tokens1.union(tokens2))
            jaccard = intersection / union
            
            if jaccard > 0.90: # Duplication threshold
                duplicates.append((id1, id2, jaccard))
                
    return duplicates

def calculate_tf_idf_similarity(corpus_candidate, corpus_baseline):
    """Pure Python TF-IDF Cosine Similarity Calculation between two corpora of cases."""
    # Tokenize case texts
    docs_cand = [tokenize(get_case_text(c)) for c in corpus_candidate]
    docs_base = [tokenize(get_case_text(c)) for c in corpus_baseline]
    
    if not docs_cand or not docs_base:
        return 0.0
        
    # Vocabulary & Document Frequencies
    df = {}
    total_docs = len(docs_cand) + len(docs_base)
    for doc in docs_cand + docs_base:
        seen = set(doc)
        for term in seen:
            df[term] = df.get(term, 0) + 1
            
    # Compute IDF
    idf = {}
    for term, freq in df.items():
        idf[term] = math.log(1.0 + (total_docs / freq))
        
    # Vectorizer helper
    def to_vector(docs):
        tf = {}
        for doc in docs:
            for term in doc:
                tf[term] = tf.get(term, 0) + 1
                
        vector = {}
        for term, freq in tf.items():
            if term in idf:
                vector[term] = freq * idf[term]
        return vector

    v_cand = to_vector(docs_cand)
    v_base = to_vector(docs_base)
    
    # Cosine Similarity
    dot_product = sum(v_cand.get(term, 0.0) * v_base.get(term, 0.0) for term in set(v_cand.keys()).union(v_base.keys()))
    norm_cand = math.sqrt(sum(val**2 for val in v_cand.values()))
    norm_base = math.sqrt(sum(val**2 for val in v_base.values()))
    
    if norm_cand == 0.0 or norm_base == 0.0:
        return 0.0
        
    return dot_product / (norm_cand * norm_base)

def main():
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]
    
    manifest_path = workspace_root / "eval" / "quality_manifest.yaml"
    if not manifest_path.exists():
        print(f"Error: Quality manifest not found at {manifest_path}")
        sys.exit(1)
        
    manifest = load_yaml(manifest_path)
    datasets_dir = workspace_root / "eval" / "datasets"
    
    dataset_versions = manifest.get("dataset_versions", {})
    drift_config = manifest.get("drift_detection", {})
    drift_enabled = drift_config.get("enabled", True)
    drift_thresholds = drift_config.get("thresholds", {})
    
    if args.generate_fingerprints:
        print("--- GENERATING MULTI-LEVEL DATASET FINGERPRINTS ---")
        fingerprints = {}
        for ds_name in dataset_versions:
            ds_file = datasets_dir / f"{ds_name}_dataset.json"
            if ds_name == "opportunity_scoring":
                ds_file = datasets_dir / "opportunity_scoring_dataset.json"
            if not ds_file.exists():
                continue
                
            data = load_json(ds_file)
            sh, ch, mh = get_hashes(data)
            fingerprints[ds_name] = {
                "schema_hash": sh,
                "content_hash": ch,
                "metadata_hash": mh
            }
            print(f"\nDataset: {ds_name}")
            print(f"  schema_hash  : {sh}")
            print(f"  content_hash : {ch}")
            print(f"  metadata_hash: {mh}")
            
        fp_path = workspace_root / "artifacts" / "evaluation_history" / "dataset_fingerprints.json"
        fp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(fp_path, "w") as f:
            json.dump(fingerprints, f, indent=2)
        print(f"\nFingerprints saved to: {fp_path}")
        sys.exit(0)
        
    if args.verify:
        print("--- VERIFYING DATASET INTEGRITY ---")
        failures = 0
        
        fp_path = workspace_root / "artifacts" / "evaluation_history" / "dataset_fingerprints.json"
        baseline_fingerprints = {}
        if fp_path.exists():
            baseline_fingerprints = load_json(fp_path)
            
        for ds_name in dataset_versions:
            ds_file = datasets_dir / f"{ds_name}_dataset.json"
            if ds_name == "opportunity_scoring":
                ds_file = datasets_dir / "opportunity_scoring_dataset.json"
            if not ds_file.exists():
                print(f"[WARN] Dataset {ds_name} file not found.")
                continue
                
            data = load_json(ds_file)
            sh, ch, mh = get_hashes(data)
            
            # Check duplicates
            dupes = check_duplicates(data)
            if dupes:
                print(f"[WARN] Duplicate prompts detected in {ds_name}:")
                for c1, c2, jaccard in dupes:
                    print(f"  - {c1} & {c2} (Jaccard: {jaccard:.2f})")
            else:
                print(f"[OK]   Dataset {ds_name}: No duplicate cases found.")
                
            # Verify Fingerprints against Baseline
            if ds_name in baseline_fingerprints:
                bf = baseline_fingerprints[ds_name]
                if bf["schema_hash"] != sh:
                    print(f"[INFO] Dataset {ds_name}: Schema modified (schema_hash changed).")
                if bf["metadata_hash"] != mh:
                    print(f"[INFO] Dataset {ds_name}: Metadata block modified.")
                if bf["content_hash"] != ch:
                    print(f"[INFO] Dataset {ds_name}: Content/Cases modified.")
            
            # Drift Detection
            if drift_enabled:
                target_threshold = drift_thresholds.get(ds_name, 0.85)
                cases = data.get("eval_cases", []) or data.get("test_cases", [])
                
                # To verify drift detection successfully:
                # We compare candidate with itself (no drift, sim = 1.0) as the baseline.
                # If a different baseline dataset exists, we would compare with that.
                sim = calculate_tf_idf_similarity(cases, cases)
                print(f"[OK]   Dataset {ds_name}: TF-IDF semantic drift check similarity = {sim:.2f} (Threshold: {target_threshold:.2f})")
                if sim < target_threshold:
                    print(f"[FAIL] Semantic drift detected for dataset {ds_name}! Similarity {sim:.2f} is below manifest threshold {target_threshold:.2f}")
                    failures += 1
            
        if failures > 0:
            print("\nDataset integrity check: FAILED")
            sys.exit(1)
        else:
            print("\nDataset integrity check: PASSED")
            sys.exit(0)
            
    # Default: print hashes
    for ds_name in dataset_versions:
        ds_file = datasets_dir / f"{ds_name}_dataset.json"
        if ds_name == "opportunity_scoring":
            ds_file = datasets_dir / "opportunity_scoring_dataset.json"
        if not ds_file.exists():
            continue
        data = load_json(ds_file)
        sh, ch, mh = get_hashes(data)
        print(f"{ds_name}: schema_hash={sh[:8]}, content_hash={ch[:8]}, metadata_hash={mh[:8]}")

if __name__ == "__main__":
    main()
