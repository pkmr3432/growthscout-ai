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

### Custom Code-Execution Metrics

#### 1. Lead Score Correctness (`lead_score_correctness`)
A deterministic Python check validating that the Opportunity Agent output lead scores exactly match the valuation heuristics formula:
*   `no_booking_widget` = +35
*   `slow_loading_mobile` = +30
*   `missing_schema_markup` = +15
*   `missing_google_analytics` = +10
*   **Expected Score Range:** `0 to 100`

---

## 4. Local Execution & Validation

Developers can validate configurations, schema correctness, and metric parsers locally:

### Run Schema and Model Compliance Tests
Ensure that all datasets conform to Pydantic definitions and JSON schemas:
```bash
PYTHONPATH=. python3 eval/run_regression_tests.py
```

### Automation Harness (`eval/run_local_eval.sh`)
An executable shell script is provided to automate the evaluation process:
```bash
./eval/run_local_eval.sh
```
This script:
1. Sets up the Python path and checks for environment configurations.
2. Dynamically configures the evaluation history output directory via the `GROWTHSCOUT_EVAL_HISTORY_DIR` environment variable (defaulting to `artifacts/evaluation_history/` if not set).
3. Switch directories into the `agents/` project folder and executes the `agents-cli eval run` command.
4. Triggers `generate_trend_report.py` to compile longitudinal quality trend metrics.
5. Triggers `generate_coverage_report.py` to update the dataset coverage report.

### Prompt Optimization (`eval/optimization_config.yaml`)
To run prompt optimization targeting custom metrics:
```bash
agents-cli eval optimize --config eval/optimization_config.yaml
```

---

## 5. Dataset Governance & Versioning

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
