# 🚀 GrowthScout AI — Evaluation Pipeline Summary

**Pipeline Run Status:** ✅ PASSED

### 📊 Metadata
| Property | Value |
| :--- | :--- |
| `evaluation_version` | `1.3.0` |
| `dataset_version` | `1.1.0` |
| `prompt_version` | `2.4.0` |
| `model_version` | `gemini-1.5-pro-002` |
| `provider` | `google` |
| `model_revision` | `2024-09-02` |
| `temperature` | `0.0` |
| `commit_hash` | `faf56a1` |
| `timestamp` | `2026-06-26T17:54:05.767740Z` |
| `pipeline_type` | `fast_ci` |

### 🔬 Quality Gate Results
| Metric | Type | Candidate | Baseline | Threshold | Status | Review Policy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `schema_validation` | deterministic | `1.0000` | `1.0000` | `1.00` | ✅ PASS | `fail_build` |
| `routing_correctness` | deterministic | `1.0000` | `1.0000` | `1.00` | ✅ PASS | `fail_build` |
| `tool_usage` | deterministic | `1.0000` | `1.0000` | `1.00` | ✅ PASS | `fail_build` |
| `state_transitions` | deterministic | `1.0000` | `1.0000` | `1.00` | ✅ PASS | `fail_build` |
| `lead_score_correctness` | deterministic | `1.0000` | `1.0000` | `1.00` | ✅ PASS | `fail_build` |
| `business_recommendation_value` | probabilistic | `0.8700` | `0.8750` | `0.85` | ✅ PASS | `warn_and_require_manual_bypass` |
| `report_readability` | probabilistic | `0.8350` | `0.8417` | `0.80` | ✅ PASS | `warn_and_require_manual_bypass` |
| `consultant_confidence_score` | probabilistic | `0.8100` | `0.8000` | `0.80` | ✅ PASS | `warn_and_require_manual_bypass` |