# Dataset Governance Policy: GrowthScout AI

This document establishes the governance policies, dataset ownership structures, lifecycle regulations, update approval workflows, and regression protection rules that govern the evaluation datasets for GrowthScout AI.

---

## 1. Evaluation-First Development Principles

GrowthScout AI enforces an **Evaluation-First Development** methodology. No agent instructions, skill prompts, or tool integration configurations may be merged into production branches without first passing baseline thresholds on the golden evaluation datasets. 
*   **Evaluation as the Source of Truth**: The golden datasets defined in `eval/datasets/` are the definitive specifications of expected system behavior.
*   **Quality Flywheel**: Every identified production issue, edge-case failure, or customer rejection must be root-caused, translated into a reproducible test record, and added to the appropriate golden dataset *before* the fix is implemented.

---

## 2. Dataset Ownership Matrix

Each golden dataset is assigned an authoritative owner responsible for maintaining schema compliance, updating reference records, and auditing target thresholds.

| Dataset Name | File Path | Authoritative Owner | Scope of Responsibility |
| :--- | :--- | :--- | :--- |
| **Discovery Dataset** | `eval/datasets/discovery_dataset.json` | Lead Discovery Engineer | Validates location query parsing, niche categorization, and search parameters. |
| **Analysis Dataset** | `eval/datasets/analysis_dataset.json` | Lead Crawling Engineer | Validates HTML scraper resilience, robots.txt parsing, and network fallback gates. |
| **Recommendation Dataset** | `eval/datasets/recommendation_dataset.json` | Lead Systems Architect | Validates actionability, domain compliance, and presence gap logic. |
| **Competitor Dataset** | `eval/datasets/competitor_dataset.json` | Principal Evaluation Engineer | Validates competitor candidates, benchmarking equations, and gap identification. |
| **Opportunity Scoring Dataset** | `eval/datasets/opportunity_scoring_dataset.json` | Principal Evaluation Engineer | Validates opportunity classifications, scoring accuracy, and confidence degradation. |
| **Workflow Test Dataset** | `eval/datasets/workflow_test_dataset.json` | Workflow Evaluation Architect | Validates orchestrator routing, partitions, timeouts, and state transitions. |
| **Memory Governance Dataset** | `eval/datasets/memory_governance_dataset.json` | Memory Governance Engineer | Validates canonical domain restrictions, ownership, and retrieval safeguards. |
| **HITL Review Dataset** | `eval/datasets/hitl_review_dataset.json` | HITL Evaluation Engineer | Validates report approval, rejection correction loops, and version increments. |
| **Security Attack Dataset** | `eval/datasets/security_attack_dataset.json` | Security Evaluation Engineer | Validates injection prevention, tool permissions, and memory/HITL bypass attempts. |

---

## 3. Golden Dataset Requirements

All records added to the golden evaluation datasets must satisfy the following criteria:
*   **Schema Enforcement**: Every dataset must contain a root-level `$schema` parameter referencing a valid JSON Schema. All records must pass schema linting.
*   **Edge-Case Coverage**: A minimum of 10% of cases in each dataset must represent explicit edge-case profiles (e.g., website down, unparseable meta tags, extreme competitor rating differentials, prompt injections).
*   **Anonymized Realism**: Test cases must reflect realistic SMB metadata (e.g., actual niches, addresses, ratings) but must be stripped of any personal PII (replacing real emails/phones with redacted placeholders).

---

## 4. Dataset Lifecycle & Archival Policy

Datasets are living resources that must evolve alongside the product roadmap.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Synthesize  │ ──> │  Active Use  │ ──> │ Deprecation  │
│  (Gen AI)    │     │  (CI Gates)  │     │ (v-Increment)│
└──────────────┘     └──────┬───────┘     └──────┬───────┘
                            │                    │
                            ▼                    ▼
                     ┌──────────────┐     ┌──────────────┐
                     │ Regression   │     │  Archival    │
                     │ Protection   │     │ (Freeze/Move)│
                     └──────────────┘     └──────────────┘
```

*   **Synthesis (Creation)**: New cases are synthesized using sandbox simulations, user feedback, or automated log parsing.
*   **Active Use**: Records are actively evaluated in the local developer CLI loops and CI pipeline release gates.
*   **Deprecation**: When system capabilities or specifications change (e.g., moving from a category model to a new classification framework), legacy records are deprecated via version control.
*   **Archival**: Deprecated records are moved into `eval/archive/` to keep active test suites highly focused and fast-executing. Archived cases are frozen to maintain historical benchmark compatibility.

---

## 5. Versioning Policy

Datasets follow a strict semantic versioning pattern:
*   **Patch Changes (e.g., 1.0.0 -> 1.0.1)**: Wording tweaks, spelling corrections, or clarifications in description fields. No changes to input parameters or expected outputs.
*   **Minor Changes (e.g., 1.0.0 -> 1.1.0)**: Addition of new test cases or edge cases within the existing schema. Does not break existing baseline tests.
*   **Major Changes (e.g., 1.0.0 -> 2.0.0)**: Modifying the JSON Schema structure, changing expected output categories, or modifying baseline thresholds. Requires full approval from the Principal Evaluation Engineer.

---

## 6. Update Approval Workflow

To modify a golden dataset:
1.  **Issue Reproduction**: The developer logs a quality issue or feature expansion.
2.  **Draft Change**: The developer updates the dataset JSON locally and validates syntax.
3.  **Run Regression Test**: The developer runs `agents-cli eval compare baseline.json candidate.json` to verify that the change does not cause regressions on unchanged tests.
4.  **Pull Request**: The change is submitted via a pull request containing a diff of the dataset and verification traces.
5.  **Owner Sign-off**: The dataset's Authoritative Owner reviews the traces and signs off on the merge.

---

## 7. Regression Protection Rules

The following rules protect the repository from quality regressions:
*   **Strict Release Gate Thresholds**: Active release gates (e.g., safety at `1.00`, opportunity classification accuracy at `>=0.95`) are absolute pass/fail bounds. A PR that degrades any metric score below the threshold is automatically blocked from merging.
*   **No Exclusion Policy**: Developers cannot skip failing test cases or mark them as optional to pass CI runs. If a test case fails, it must either be fixed by adjusting prompts/logic, or the dataset itself must be formally modified via the Update Approval Workflow if specifications have shifted.
*   **Execution Time Limits**: Local test suites must run in under 5 minutes to maintain developer velocity. If a dataset grows too large, older standard cases are archived in favor of new edge cases.

---

## 8. Dataset Audit and Review Process

The evaluation dataset bank is subjected to a bi-annual audit review:
*   **Grounded Evaluation**: Checking whether the expected outputs in datasets match actual production logs for approved report templates.
*   **Drift Analysis**: Confirming that test cases remain representative of actual user search queries and local market distributions.
*   **Redundancy Audits**: Pruning redundant test cases that test the same code paths, moving them to the archival bank to optimize run-time.
