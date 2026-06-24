# Evaluation Specification: GrowthScout AI

This document establishes the evaluation-first testing rules, metric parameters, dataset requirements, and performance gates that govern code quality for GrowthScout AI.

---

## 1. Core Evaluation Metrics

Every agent execution, skill trace, and workflow routing plan is evaluated against the following core metrics before production deployments:

| Metric Name | Type | Measurement Scope |
| :--- | :--- | :--- |
| `multi_turn_task_success` | LLM-as-Judge | Measures whether the Orchestrator successfully satisfied the user's intent. |
| `multi_turn_tool_use_quality` | LLM-as-Judge | Checks if tools were selected correctly, called with valid arguments, and handled responses appropriately. |
| `multi_turn_trajectory_quality`| LLM-as-Judge | Measures the efficiency of the routing path (e.g., no redundant scraping or repeated calls). |
| `final_response_quality` | LLM-as-Judge | Rates report outputs for readability, professional tone, specificity, and grammatical correctness. |
| `hallucination` | LLM-as-Judge | Assesses the grounding of recommendations in crawler outputs. Score ranges from `0` (grounded) to `1` (completely hallucinated). |
| `safety` | LLM-as-Judge | Ensures zero violations of system prompts, injection attempts, or unauthorized access attempts. |
| `business_impact_quality` | LLM-as-Judge | Measures whether technical findings are translated into meaningful business outcomes. |
| `opportunity_classification_accuracy` | LLM-as-Judge / Exact | Measures correctness of mapping detected presence gaps into the 8 approved opportunity categories. |
| `opportunity_scoring_accuracy` | LLM-as-Judge / Heuristic | Measures correctness, transparency, and explainability of generated opportunity scores. |
| `competitive_insight_quality` | LLM-as-Judge | Measures quality, mathematical precision, and relevance of competitor benchmarks and gap comparisons. |
| `evidence_traceability` | LLM-as-Judge / Lint | Measures whether outputs contain source references, tool execution references, and confidence metadata. |
| `memory_validation_score` | LLM-as-Judge / Lint | Measures compliance with memory ownership, canonical memory domains, immutable audit history, and report versioning rules. |
| `routing_integrity_score` | LLM-as-Judge / Lint | Measures compliance with workflow routing governance, HITL routing rules, no-website branching, and failure recovery paths. |

### Workflow-Level Evaluation Metrics

```yaml
workflow_metrics:
  workflow_completion_rate:
    description: "Measures successful completion of the workflow from IDLE to COMPLETED."
  workflow_recovery_quality:
    description: "Measures ability to recover from failures, timeouts, and resume execution."
  hitl_compliance:
    description: "Measures adherence to mandatory Human-in-the-Loop review gates."
  memory_governance_compliance:
    description: "Measures adherence to memory ownership and write restrictions."
```

---

## 2. Evaluation Datasets Requirements

The repository maintains five mandatory golden datasets in `eval/datasets/` that must be fully prepared as reference benchmarks before implementation begins:

1.  **`discovery_dataset.json`**: Tests the search query formulation, geographic coordinate translation, and business filter rules.
2.  **`analysis_dataset.json`**: Contains simulated web scraping HTML structures (some with broken links, robots.txt blocks, and redirect headers) to test crawler resilience.
3.  **`recommendation_dataset.json`**: Mocks business presence profile gaps, asserting that recommendations are factual and actionable.
4.  **`competitor_dataset.json`**: Contains target businesses, competitor candidates, and expected benchmark calculations to test competitive intelligence accuracy.
5.  **`opportunity_scoring_dataset.json`**: Contains verified website audit logs, expected opportunity classifications, expected score ranges, and expected confidence levels.

### Dataset Coverage Requirements

```yaml
dataset_coverage_requirements:
  minimum_cases:
    discovery_dataset: 100
    analysis_dataset: 100
    recommendation_dataset: 100
    competitor_dataset: 100
    opportunity_scoring_dataset: 100
  required_edge_cases:
    - no_website_business
    - robots_txt_blocked
    - website_timeout
    - invalid_schema_markup
    - missing_metadata
    - missing_competitor_data
    - conflicting_competitor_signals
    - incomplete_audit_logs
    - hitl_rejection_loop
    - memory_ownership_violation
    - unauthorized_memory_write
    - report_version_conflict
    - orchestrator_bypass_attempt
    - worker_to_worker_transition_attempt
    - no_website_branch_execution
    - workflow_resume_after_failure
```

---

## 3. Local and Remote Testing Cycle

```
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Local Edit   │ ──> │ agents-cli   │ ──> │ agents-cli   │
  │ of Prompts   │     │ eval generate│     │ eval grade   │
  └──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │ (Check results.html)
                                                   ▼
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Merge to Main│ ◄── │ CI/CD Remote │ ◄── │ Compare      │
  │ Deployment   │     │ eval submit  │     │ results.json │
  └──────────────┘     └──────────────┘     └──────────────┘
```

1.  **Local Execution**: Developers run `agents-cli eval run` locally. This command runs inference over the dataset, saves trajectories in `artifacts/traces/`, and grades them against rules in `eval/eval_config.yaml`.
2.  **Compare Regression**: After adjustments, developers execute `agents-cli eval compare baseline.json candidate.json` to confirm quality improvements.
3.  **CI/CD Pipeline Gate**: The GitHub Actions runner executes `agents-cli eval submit --dataset <path>` to run cloud-side evaluations on the Vertex AI Evaluation Service.

---

## 4. Release Threshold Gates (Pass/Fail)

A Pull Request cannot be merged into `main` if the evaluation run fails any of the following gates:

```yaml
release_thresholds:
  safety: "1.00"
  multi_turn_task_success: ">=0.85"
  multi_turn_tool_use_quality: ">=0.90"
  global_hallucination: "<=0.10"
  final_response_quality: ">=0.80"
  business_impact_quality: ">=0.85"
  opportunity_classification_accuracy: ">=0.95"
  opportunity_scoring_accuracy: ">=0.90"
  competitive_insight_quality: ">=0.85"
  evidence_traceability: ">=0.95"
  opportunity_agent_hallucination: "==0.00" # Enforced strictly on Opportunity Agent reasoning outputs
  workflow_completion_rate: ">=0.90"
  workflow_recovery_quality: ">=0.85"
  hitl_compliance: "1.00"
  memory_governance_compliance: "1.00"
  memory_validation_score: "1.00"
  routing_integrity_score: "1.00"
```

---

## 5. Agent-Specific Evaluation Gates

Each agent must satisfy its respective threshold criteria during automated evaluation runs:

```yaml
agent_thresholds:
  orchestrator_agent:
    multi_turn_task_success: ">=0.85"
    multi_turn_trajectory_quality: ">=0.90"
  business_discovery_agent:
    multi_turn_tool_use_quality: ">=0.90"
  website_analysis_agent:
    hallucination: "<=0.05"
  opportunity_agent:
    hallucination: "==0.00" # Must be 100% grounded in crawler outputs
    opportunity_classification_accuracy: ">=0.95"
    opportunity_scoring_accuracy: ">=0.90"
  growth_intelligence_agent:
    final_response_quality: ">=0.88"
    evidence_traceability: ">=0.95" # Must contain full citation back-references
```

---

## 6. Skill-Level Evaluation Matrix

Every active skill package must satisfy the metric quality gates defined in `skill_architecture.md`:

```yaml
skill_thresholds:
  business-discovery:
    format: "JSON array validation"
    min_leads_retrieved: ">=3"
    min_competitors_retrieved: ">=3"
  website-analysis:
    robots_txt_classification_accuracy: "1.00"
    error_handling: "graceful_fallback"
  seo-audit:
    tag_extraction_hallucination: "==0.00"
  competitor-analysis:
    baseline_benchmarking_accuracy: "1.00"
  opportunity-classification:
    classification_accuracy: ">=0.95"
  opportunity-scoring:
    score_accuracy: ">=0.90"
    evidence_traceability: ">=0.95"
    confidence_reasoning_required: true
  business-impact-analysis:
    business_impact_quality: ">=0.85"
    jargon_only_blocked: true
  growth-report-generation:
    final_response_quality: ">=0.82"
    evidence_traceability: ">=0.95"
  outreach-generation:
    tone_adherence: ">=0.85"
    pii_redaction_compliance: "1.00"
  local-business-research:
    metadata_extraction_accuracy: "1.00"
```

---

## 7. Evidence Grounding & Hallucination Testing

The evaluation framework automatically fails any trace where unsupported claims appear. Grounding verification rules must enforce:

```yaml
grounding_requirements:
  opportunity_scores_must_cite_evidence: true
  recommendations_must_cite_opportunities: true
  competitive_findings_must_cite_snapshots: true
  reports_must_include_traceable_references: true
  missing_evidence_must_reduce_confidence_or_block: true
```

### Verification Directives:
1.  **Opportunity Scores Evidence**: Scores must explicitly cite the `audit_history` data logs that influenced calculations.
2.  **Recommendations Context**: Growth recommendations must trace back to classified opportunities in `opportunity_history`.
3.  **Competitive Findings Context**: Benchmark tables must trace back to direct competitor logs in `competitor_snapshots`.
4.  **Report Traceability**: Every section of the compiled Markdown report must reference source database snap-keys.
5.  **Missing Evidence Penalty**: If tool execution logs are unavailable, opportunity scoring must block output generation. Missing secondary parameters (e.g. partial crawling tags) must reduce confidence level ratings applying the degradation penalties.

---

## 8. Memory Governance Validation

The purpose of this section is to ensure that the memory architecture defined in `memory_bank_config.yaml` is continuously validated through automated evaluation.

```yaml
memory_validation_requirements:
  canonical_domain_validation: true
  ownership_enforcement_validation: true
  unauthorized_write_detection: true
  append_only_audit_history_validation: true
  report_versioning_validation: true
```

*   **Canonical domain validation** verifies that all workflow writes target approved memory domains.
*   **Ownership enforcement validation** verifies agents only write to memory domains they own.
*   **Unauthorized write detection** verifies violations are blocked and routed to FAILED state.
*   **Append-only audit history validation** verifies audit records cannot be modified after creation.
*   **Report versioning validation** verifies regenerated reports create new versions rather than overwriting historical reports.

---

## 9. Workflow Routing Integrity Validation

The purpose of this section is to ensure workflow routing remains compliant with the orchestrator-only governance model.

```yaml
routing_integrity_requirements:
  orchestrator_only_transitions: true
  no_worker_to_worker_routing: true
  no_website_branch_validation: true
  hitl_rejection_loop_validation: true
  failure_recovery_validation: true
```

*   **Orchestrator-only transitions** verify that all state transitions are evaluated and approved by the Orchestrator Agent.
*   **No worker-to-worker routing** verifies agents never invoke each other directly.
*   **No-website branch validation** verifies businesses without websites bypass auditing and route directly into Opportunity Analysis.
*   **HITL rejection loop validation** verifies rejected reports route back into Report Generation using human feedback.
*   **Failure recovery validation** verifies workflow recovery from timeout, cancellation, and restart scenarios.
