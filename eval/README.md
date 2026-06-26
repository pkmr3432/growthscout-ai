# GrowthScout AI — Evaluation & Quality Framework

This directory houses the evaluation datasets, custom LLM metrics, validation engines, and quality policies that govern agent development for GrowthScout AI.

---

## 1. Overview & Quality Flywheel

GrowthScout AI enforces a strict **Evaluation-First Development** workflow based on the **Quality Flywheel** standard. No prompts, instructions, routing logic, or tool mappings may be merged without meeting quality release gates on the golden benchmark datasets.

```

  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Local Prompt │ ──> │  agents-cli  │ ──> │  agents-cli  │
  │ Adjustments  │     │ eval generate│     │  eval grade  │
  └──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │ (Check results.html)
                                                   ▼
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Merge to Main│ ◄── │  CI/CD Gate  │ ◄── │  Compare     │
  │ (Staging/PE) │     │ eval submit  │     │ results.json │
  └──────────────┘     └──────────────┘     └──────────────┘
```

---

## 2. Dataset Inventory

The framework maintains five mandatory golden datasets for core agent tasks, plus specialized operational verification datasets:

| Dataset File | Target Component | Cases | Purpose / Scope |
| :--- | :--- | :--- | :--- |
| [`discovery_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/discovery_dataset.json) | Discovery Agent | 30 | Validates coordinate parsing, local niche keywords, and lead count constraints. |
| [`analysis_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/analysis_dataset.json) | Web Analyzer Agent | 30 | Simulates site timeouts, Robots.txt blocks, CMS detections, and scraping limits. |
| [`recommendation_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/recommendation_dataset.json) | Growth Agent | 30 | Validates actionability, domain compliance, and presence gap logic in report draft prompts. |
| [`competitor_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/competitor_dataset.json) | Competitor Analysis | 30 | Validates local competitor cohort benchmarking, averages, and gap calculations. |
| [`opportunity_scoring_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/opportunity_scoring_dataset.json) | Opportunity Agent | 30 | Asserves score heuristics correctness, category mapping, and confidence degradation. |
| [`memory_governance_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/memory_governance_dataset.json) | Memory System | 7 | Verifies canonical domains, write permissions, and read confidence filters. |
| [`workflow_test_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/workflow_test_dataset.json) | Workflow Orchestrator | 8 | Validates Orchestrator state routing, retry counts, and HITL rejection loops. |
| [`hitl_review_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/hitl_review_dataset.json) | Human-in-the-Loop | 5 | Ensures rejected reports route back for corrections using feed-forward logs. |
| [`security_attack_dataset.json`](file:///Users/ptech/Desktop/growthscout-ai/eval/datasets/security_attack_dataset.json) | Security Sandbox | 7 | Verifies protection against prompt injections, API bypasses, and memory exploits. |

---

## 3. Metrics Pool

We run a combination of built-in Agent Platform metrics and custom domain-specific judges defined in [`eval_config.yaml`](file:///Users/ptech/Desktop/growthscout-ai/eval/eval_config.yaml):

### Custom LLM-as-a-Judge Metrics

#### 1. Business Recommendation Value (`business_recommendation_value`)
Evaluates report recommendations for business consulting relevance, actionability, prioritization, impact logic, and usefulness.
*   **Grading Criteria (1 to 5):**
    1.  **Relevance:** Are recommendations directly aligned with business niche constraints and gaps?
    2.  **Actionability:** Are recommendations clear and executable by non-technical SMB owners?
    3.  **Prioritization:** Are higher-scoring gaps prioritized in the report hierarchy?
    4.  **Business Impact Explanation:** Does the report translate findings into business consequences?
    5.  **Consulting Usefulness:** Can a consultant present this report without manual editing?
*   **Score Calculation:** The judge returns scores for each of the 5 criteria. The final metric is the average of these sub-scores divided by 5 (normalized on a `0.0 to 1.0` scale).
*   **PR Quality Gate:** `>= 0.85`

#### 2. Report Readability & Communication Quality (`report_readability`)
Measures the tone, structure, and clarity of compiled markdown reports.
*   **Grading Criteria (1 to 5):**
    1.  **Organization & Flow:** Clear heading hierarchy, logical progression.
    2.  **Clarity:** Plain language, avoiding overly complex technical jargon.
    3.  **Conciseness:** Minimal repetition, no circular descriptions.
    4.  **Professional Tone:** Consultative, encouraging, and authoritative.
*   **Score Calculation:** The judge returns scores for each of the 4 criteria. The final metric is the average of these sub-scores divided by 5 (normalized on a `0.0 to 1.0` scale).
*   **PR Quality Gate:** `>= 0.80`

#### 3. Consultant Confidence Score (`consultant_confidence_score`)
Assesses whether an experienced freelance consultant would confidently deliver the generated report to a paying client without significant manual edits.
*   **Grading Criteria (1 to 5):**
    1.  **1 (Unacceptable)**: Major errors in spelling/grammar, broken formatting, missing sections, or completely inaccurate/hallucinated findings. Requires a complete rewrite.
    2.  **2 (Poor)**: Accurate raw data but poorly styled or structured, has a cold/generic tone, or has minor hallucinations. Needs extensive manual revisions.
    3.  **3 (Average)**: Contains useful findings and correct data, but lacks professional consulting depth, minor formatting inconsistencies, or robotic phrasing. Requires moderate editing.
    4.  **4 (Good)**: High-quality report, professional tone, clean structure, action-oriented insights. Needs only minor cosmetic changes or small wording tweaks.
    5.  **5 (Excellent)**: Outstanding insights, perfect structure, tailored tone, and immaculate presentation. Ready to deliver immediately without any modifications.
*   **Score Calculation:** Normalized linearly: `Score = (Rubric Rating) / 5` (on a `0.0 to 1.0` scale).
*   **PR Quality Gate:** `>= 0.80` (representing a score of 4 or 5 stars).

### Custom Code-Execution Metrics

#### 1. Lead Score Correctness (`lead_score_correctness`)
A deterministic Python check validating that the Opportunity Agent output lead scores exactly match the valuation heuristics formula:
*   `no_booking_widget` = +35
*   `slow_loading_mobile` = +30
*   `missing_schema_markup` = +15
*   `missing_google_analytics` = +10
*   **Expected Score Range:** `0 to 100`

---

## 4. Quality Manifest (`eval/quality_manifest.yaml`)

We introduce an authoritative quality configuration file at `eval/quality_manifest.yaml`. This acts as the single source of truth for:
*   **Dataset versions** and active **baseline references** (e.g. `sprint_6.2_baseline.json`).
*   **Cadence-based case limits** (e.g. running 5 cases per dataset in Fast CI vs 30 cases in Full Nightly).
*   **Gating parameters** for both deterministic and probabilistic metrics.

Deterministic metrics (such as schema validation or lead score correctness) enforce hard failures (`Exit Code 1`). Probabilistic metrics evaluated via LLM judges support configurable thresholds and soft review policies (e.g. `"trigger_secondary_judge"` or `"warn_and_require_manual_bypass"`) to eliminate build blockages due to model variance.

---

## 5. Dual-Pipeline Architecture

Evaluation execution is divided into two pipelines to balance feedback speed with thoroughness:

### A. Fast CI Pipeline (Pull Requests)
*   **Trigger**: Automatically executed on pull requests targeting `main` or release branches.
*   **Scope**: Runs pytest suite, regression contract validation (`run_regression_tests.py`), and executes evaluation on a **subset of 5 cases per golden dataset** for fast developer feedback.
*   **Gate Behavior**: Enforces deterministic metrics (fails on violation) but logs warnings for probabilistic failures without blocking the build.
*   **Execution Time Target**: `< 3` minutes.

### B. Full Evaluation Pipeline (Nightly & Releases)
*   **Trigger**: Nightly schedule cron job (`0 2 * * *`) or on release tag pushes (`v*`).
*   **Scope**: Evaluates the **complete 150-case golden dataset** (30 cases per dataset), compiles trend logs (`generate_trend_report.py`), updates the coverage report, and generates the HTML dashboard.
*   **Gate Behavior**: Enforces both deterministic and probabilistic gates. Blocks release on any failure unless bypassed.
*   **Execution Time Target**: `< 15` minutes.

---

## 6. Local Execution & Validation

Developers can validate configurations, schema correctness, and pipeline execution locally.

### Automation Harness (`eval/run_local_eval.sh`)
Execute the harness with the desired pipeline option:

*   **Run Fast CI pipeline**:
    ```bash
    ./eval/run_local_eval.sh --pipeline fast
    ```
*   **Run Full Evaluation pipeline**:
    ```bash
    ./eval/run_local_eval.sh --pipeline full
    ```

The harness will:
1.  Verify `.env` configuration and setup the python path.
2.  Filter datasets to the configured subset (for fast pipeline) or load full datasets (for full pipeline).
3.  Run evaluation grading using `agents-cli eval run`.
4.  Run `compare_ci_regression.py` to compare against baseline scores and apply gate rules.
5.  Run `generate_ci_report.py` to compile Markdown summaries, JSON records, and HTML dashboards containing the structured metadata payload.

### Manual Bypass Workflow
To bypass probabilistic gate blocks during a Full Evaluation release build:
```bash
export BYPASS_PROBABILISTIC_GATES=true
./eval/run_local_eval.sh --pipeline full
```
This forces the comparison engine to log the violations as warnings but exit with code 0.

---

## 7. Dataset Governance & Versioning

All datasets are versioned under git. Modifying dataset cases requires adhering to standard schemas, metadata specifications, and review workflows.

### A. Case ID Naming Conventions
Evaluation case identifiers follow a deterministic pattern: `[COMPONENT]-[SOURCE]-[NUM]`
*   **Component Prefix**:
    *   `DISC` for Discovery
    *   `ANAL` for Web Analysis
    *   `RECO` for Recommendation
    *   `COMP` for Competitor Analysis
    *   `OPPS` for Opportunity Scoring
*   **Source Prefix**:
    *   `M` for Manual (e.g., Sprint 6.1 baseline cases)
    *   `S` for Synthesized (e.g., Sprint 6.2 simulation cases)
*   **Counter**: A 3-digit serial number (e.g., `001` to `030`).
*   *Examples*: `DISC-M-001`, `ANAL-S-026`.

### B. Synthesized-Case Validation Pipeline
All generated evaluation cases undergo a five-stage pipeline before promotion into the golden dataset files:
1.  **Generation**: User simulation executes queries locally and outputs trace records.
2.  **Schema Validation**: The case must validate successfully against the corresponding Draft-07 JSON Schema.
3.  **Duplicate Detection**: Check similarity of prompts and inputs against existing cases to prevent redundant coverage.
4.  **Manual Review**: Developer reviews the validity of the inputs and feasibility of the simulated scenario.
5.  **Quality Review**: Verify that expected outputs or scores are mathematically consistent and trace references conform to valuation heuristics.

### C. Compare & Prune Workflow
1.  Executing a regression compare run:
    ```bash
    agents-cli eval compare baseline.json candidate.json
    ```
2.  Pruning outdated or redundant cases by archiving them under `eval/archive/` to keep evaluation suite execution times under 5 minutes.

---

## 8. Evaluation Contract Reference

The quality gates, datasets, and metrics are governed by the authoritative [EVALUATION_CONTRACT.md](file:///Users/ptech/Desktop/growthscout-ai/eval/EVALUATION_CONTRACT.md). All modifications to the evaluation framework or datasets must preserve backward compatibility as guaranteed in the contract.

---

## 9. Regression Diagnostics

When quality gates fail, `regression_diagnostics.py` runs automatically to explain the failure. It cross-references git status changes with metric drops to categorize regressions into:
*   **Prompt Regression**: Drop in scores correlated with modifying agent instruction scripts.
*   **Dataset Regression**: Drop in scores due to modifications in the golden dataset files.
*   **Configuration Regression**: Tweaks in manifest or configuration parameters.
*   **Model Regression**: Drop in scores due to upstream model or API variations.
*   **Tool Regression**: Changes made to MCP schemas or tool descriptions.
*   **Schema Regression**: Variations in core Pydantic schemas or converters.
*   **Infrastructure Regression**: CI/CD config or docker modifications.
*   **Dependency Regression**: Package changes in lockfiles.
*   **Evaluation Regression**: Score changes resulting from grader/rubric prompt edits.

---

## 10. Prompt Optimization Safety Workflow

Automated prompt tuning must strictly remain Human-in-the-Loop:
1.  Run `python3 eval/optimize_prompts.py --dry-run` to verify optimization config.
2.  The optimizer outputs candidate prompts and logs side-by-side A/B score comparisons to `artifacts/evaluation_history/candidate_prompts.json`.
3.  Active production prompt files are **never** automatically overwritten. The developer must manually review, approve, commit, and PR the modified prompt.

