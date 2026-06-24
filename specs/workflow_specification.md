# Workflow Specification: GrowthScout AI

This document defines the multi-agent workflow state machine, routing logic, parallel execution rules, and Human-in-the-Loop (HITL) checkpoints for the growth intelligence compilation process.

---

## 1. Workflow Pipeline State Machine

The core GrowthScout AI pipeline executes across 8 distinct states:

```
                  ┌──────────────────────┐
                  │       1. IDLE        │
                  └──────────┬───────────┘
                             │ (User Search Request)
                             ▼
                  ┌──────────────────────┐
                  │    2. DISCOVERING    │
                  └──────────┬───────────┘
                             │ (Leads & Competitors discovered)
                             ▼
                  ┌──────────────────────┐
                  │3. ROUTE_AUDITING_... │ (Partition Leads)
                  └──────────┬───────────┘
                             │
         ┌───────────────────┴───────────────────┐
         │ (Website Leads)                       │ (No-Website Leads)
         ▼                                       │
  ┌──────────────┐                               │
  │ 4. AUDITING  │◄─── (Iterates in parallel)    │
  └──────┬───────┘                               │
         │ (Crawls done)                         │
         └───────────────────┬───────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │5. OPPORTUNITY_ANALY..│ (Evidence Validation Gate)
                  └──────────┬───────────┘
                             │ (Scores, Impact & Benchmarks ready)
                             ▼
                  ┌──────────────────────┐
                  │ 6. REPORT_GENERATION │◄────────────────┐
                  └──────────┬───────────┘                 │
                             │ (Growth Report generated)   │ (Human
                             ▼                             │  Rejection
                  ┌──────────────────────┐                 │  Loop)
                  │ 7. AWAITING_APPROVAL │─────────────────┘
                  └──────────┬───────────┘
                             │ (User Approved Callback)
                             ▼
                  ┌──────────────────────┐
                  │     8. COMPLETED     │
                  └──────────────────────┘
```

---

## 2. State Transition Protocols

### State 1: IDLE to DISCOVERING
*   **Trigger**: API Gateway sends a batch analysis request payload containing `niche`, `location`, and optional limits.
*   **Action**: Orchestrator initializes `session_state`, creates a unique `session_id`, and dispatches the local search request to the `Business Discovery Agent`.

### State 2: DISCOVERING to ROUTE_AUDITING_OR_ANALYSIS
*   **Trigger**: Discovery agent returns target leads and direct competitor candidate profiles.
*   **Action**: Orchestrator persists the discovered leads and competitor candidates in `session_memory`.

### State 3: ROUTE_AUDITING_OR_ANALYSIS (Lead Partitioning)
*   **Trigger**: Partitioning rules evaluate discovered leads.
*   **Action**: The Orchestrator splits leads into `website_leads` and `no_website_leads` partitions, persisting them in `session_memory`. If website leads exist, it routes to `AUDITING`. If only no-website leads exist, it routes directly to `OPPORTUNITY_ANALYSIS`.

### State 4: AUDITING to OPPORTUNITY_ANALYSIS
*   **Trigger**: Website Analysis Agent completes auditing tags, speed metrics, and schema structures on all target and competitor websites.
*   **Action**: Orchestrator aggregates all raw crawling outputs into the `audit_history` memory domain and transitions to Opportunity Analysis.

### State 5: OPPORTUNITY_ANALYSIS (Reasoning Gate)
*   **Trigger**: Verification of evidence parameters.
*   **Evidence Validation Gate**: Before opportunity scoring begins, the Orchestrator enforces that the `Opportunity Agent` verifies:
    *   *Verified audit logs* exist in the `audit_history` memory domain.
    *   *Confidence metadata* is attached to incoming snapshots.
    *   *Source references* (the tool execution logs) are present.
    If audit evidence is missing or unverified, the Opportunity Agent blocks scoring on that lead to prevent hallucination.
*   **Action**: The Opportunity Agent executes the following tasks in sequence:
    1.  **No-Website Classification**: If target has no domain, it is classified as "No Website Opportunity" (skipping web crawls but evaluating reputation and local maps metrics).
    2.  **Opportunity Classification**: Maps verified digital presence gaps to one of the 8 formal categories.
    3.  **Competitive Benchmarking**: Compiles comparative benchmarks comparing target metrics against competitor candidate profiles.
    4.  **Business Impact Analysis**: Translates technical gaps into business outcomes (estimated traffic loss, conversion gaps).
    5.  **Opportunity Scoring & Confidence Assessment**: Generates `opportunity_score`, `confidence_score` (`High`/`Medium`/`Low`), and `confidence_reasoning` applying **Confidence Degradation Rules**.
    Upon completion, writes outputs to `opportunity_history` and `competitor_snapshots` memory domains.

### State 6: OPPORTUNITY_ANALYSIS to REPORT_GENERATION
*   **Trigger**: Opportunity scoring, classification, and impact records successfully committed.
*   **Action**: The Orchestrator invokes the `Growth Intelligence Agent` to compile the primary **Growth Intelligence Report** as the primary output. Once the report is generated, the agent may optionally generate secondary artifacts (such as outreach messages and proposal drafts) based *only* on the finalized report findings.

### State 7: REPORT_GENERATION to AWAITING_APPROVAL
*   **Trigger**: Master Growth Intelligence Report and optional secondary proposals successfully drafted and saved to `growth_reports`.
*   **Action**: Orchestrator marks the session status as `awaiting_approval` and holds execution until a human review callback is received.

### State 8: AWAITING_APPROVAL to COMPLETED (or Rejection Loop)
*   **Trigger**: Gateway receives callback payload from the human user.
*   **Human Review Rejection Flow**: If the human reviewer rejects the report (or issues a correction request):
    1.  The Orchestrator captures the reviewer feedback text.
    2.  The Orchestrator writes the feedback into the `human_notes` memory domain.
    3.  The Orchestrator routes the execution back to the `REPORT_GENERATION` state.
    4.  The Growth Intelligence Agent reads the feedback from `human_notes` and regenerates the Growth Intelligence Report using the approved corrections, applying **Growth Report Versioning** rules.
*   **Trigger (Approval)**: Gateway receives an `approved` payload.
*   **Action**: Orchestrator writes the finalized report to the persistent business knowledge base, purges the ephemeral `session_memory` session logs, and marks the session as `COMPLETED`.

---

## 3. State Memory Output Matrix

During workflow transitions, write operations must be restricted strictly to the following canonical memory domains:

| Workflow State | Written Memory Domains | Read Memory Domains | Authoritative Owner |
| :--- | :--- | :--- | :--- |
| **DISCOVERING** | `session_memory`, `business_profiles` | `session_memory` | `business_discovery_agent` |
| **ROUTE_AUDITING_OR_ANALYSIS** | `session_memory` | `session_memory` | `orchestrator_agent` |
| **AUDITING** | `session_memory`, `audit_history` | `session_memory`, `business_profiles` | `website_analysis_agent` |
| **OPPORTUNITY_ANALYSIS** | `session_memory`, `opportunity_history`, `competitor_snapshots` | `session_memory`, `business_profiles`, `audit_history` | `opportunity_agent` |
| **REPORT_GENERATION** | `session_memory`, `growth_reports` | `session_memory`, `business_profiles`, `audit_history`, `opportunity_history`, `competitor_snapshots`, `human_notes` | `growth_intelligence_agent` |
| **AWAITING_APPROVAL** | `session_memory`, `human_notes` | `session_memory`, `growth_reports` | `human_user` |

---

## 4. Confidence Degradation Rules

Confidence levels calculated during Opportunity Scoring must apply the following degradation penalties based on evidence completeness:

*   **Missing Competitor Data**: Degrade confidence by one level (e.g. `High` $\rightarrow$ `Medium`).
*   **Failed Website Audit**: Degrade confidence to `Low` (since presence metrics cannot be verified).
*   **Incomplete SEO Audit**: Degrade confidence by one level (e.g. `High` $\rightarrow$ `Medium`).
*   **Missing Verified Evidence**: The *Evidence Validation Gate* fails completely. Opportunity scoring is **blocked and aborted** for that lead to prevent hallucination.

---

## 5. Workflow Success Criteria

To transition between states, the following quality metrics must be satisfied:

*   **DISCOVERING**: At least 1 target lead and $\ge 3$ competitor candidates resolved and stored.
*   **AUDITING**: Crawler successfully parses robots.txt and HTML structures for $\ge 80\%$ of target and competitor domains (excluding "No Website" targets).
*   **OPPORTUNITY_ANALYSIS**: 100% of discovered presence gaps classified into the 8 categories, and opportunity score, confidence score, and confidence reasoning committed.
*   **REPORT_GENERATION**: Master Markdown Growth Intelligence Report generated, containing all structured sections, evidence citations, and traceability references, saved to `growth_reports`.

---

## 6. Parallel Processing & Concurrency Rules

*   **Concurrency Batching**: Maximum concurrent audits are limited to **5 domains** in parallel to avoid rate limiting and IP blocks on local websites.
*   **Isolation of Failures**: If a single URL crawl fails, its audit result is marked as `failed` with error metadata, but the orchestrator must proceed with analysis for other successful domains.
*   **Scored Domain Bounds**: Only the approved memory domains (`audit_history`, `competitor_snapshots`) may influence opportunity scoring calculations. No unverified external memories or general LLM assumptions are permitted.

---

## 7. Error Handling and State Recovery

*   **State Serialization**: The active execution state must be saved to the database on every state transition.
*   **Timeout Handling**: If any worker agent hangs for more than 60 seconds during a turn, the orchestrator terminates the transaction, registers a `timeout_error` in the logs, and falls back to the previous stable state.
*   **Resume Capability**: If execution halts unexpectedly, the framework reads the serialized session context from Firestore and resumes from the last successfully completed state.

---

## 8. Explicit No-Website Workflow Branch

When a discovered local business lacks an online domain, it is routed through a dedicated branch to skip crawling but preserve opportunity scoring for evaluation:

```yaml
no_website_branch:
  condition:
    website_url: null
  skip_states:
    - AUDITING
  route_to:
    - OPPORTUNITY_ANALYSIS
```

### Routing and Evidence Handling Rules:
*   If `website_url` is missing or null, the Orchestrator completely skips the `AUDITING` state.
*   The Orchestrator routes execution directly from `DISCOVERING` to `OPPORTUNITY_ANALYSIS`.
*   No crawler execution or HTTP request is attempted for non-existent domains.
*   Only the **No Website Opportunity** category may be generated from the website absence itself.
*   Other opportunity calculations (e.g. Reputation Opportunity) must use maps reviews, location coordinates, and business profile metadata from `business_profiles` as their evidence inputs.

---

## 9. Growth Report Versioning

To ensure revision history is preserved, all updates and regenerations of Growth Intelligence Reports must be version-controlled:

```yaml
report_versioning:
  enabled: true
  initial_version: v1
  increment_on_regeneration: true
  retain_previous_versions: true
```

### Versioning Governance Rules:
*   Every compiled Growth Intelligence Report must be assigned a version identifier.
*   The initial report draft generated is versioned as `v1`.
*   Every subsequent regeneration caused by a Human-in-the-Loop rejection increments the version suffix (e.g., `v1` $\rightarrow$ `v2`).
*   All previous report records must remain preserved in the `growth_reports` canonical domain and never be overwritten or deleted.

---

## 10. Workflow Audit Trail

The Orchestrator must enforce immutable traceability for all agent operations and state transitions:

```yaml
workflow_audit_trail:
  immutable: true
  required_fields:
    - session_id
    - workflow_state
    - acting_agent
    - timestamp
    - input_references
    - output_references
    - transition_reason
```

### Audit Logging Rules:
*   Every single state transition must write an audit record to the `session_memory` domain.
*   Audit log entries must contain the exact fields listed under `required_fields`.
*   Audit records are immutable and append-only to prevent tampering.
*   All opportunity scores and compiled reports must maintain references back to the raw audit logs that served as their evidence foundations.
