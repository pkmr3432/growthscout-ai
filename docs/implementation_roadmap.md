# Implementation Roadmap: GrowthScout AI

This document outlines the 10-phase implementation roadmap for transitioning the GrowthScout AI platform from the zero-implementation specification stage (Phase 0) to a production-ready system. 

The roadmap strictly follows the **Specification → Architecture → Skills → Agents → Workflows → Evaluation → Security → Implementation** hierarchy.

---

## Roadmap Phases Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │  Phase 1: MCP Infrastructure   │   Phase 2: Skill Packages  │
 ├────────────────────────────────┼────────────────────────────┤
 │  Phase 3: Agent Definition     │   Phase 4: Workflow Orche  │
 ├────────────────────────────────┼────────────────────────────┤
 │  Phase 5: Memory Integration   │   Phase 6: Eval Integration│
 ├────────────────────────────────┼────────────────────────────┤
 │  Phase 7: Security Validation  │   Phase 8: Frontend Gate   │
 ├────────────────────────────────┼────────────────────────────┤
 │  Phase 9: E2E Integration      │   Phase 10: Prod Readiness │
 └─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: MCP Infrastructure Implementation
*   **Goal**: Establish the sandboxed external tool servers that provide discovery and crawling capabilities.
*   **Actions**:
    1.  Implement the `local_search_server` to connect Maps API endpoints with the schema contract defined in [local_search_contract.yaml](file:///Users/ptech/Desktop/growthscout-ai/mcp/contracts/local_search_contract.yaml).
    2.  Implement the `web_analyzer_server` using standard headless scraping libraries (e.g., Playwright) and validate outputs against [web_analyzer_contract.yaml](file:///Users/ptech/Desktop/growthscout-ai/mcp/contracts/web_analyzer_contract.yaml).
    3.  Implement stdout/stdin communication protocols in the MCP server setups.
*   **Exit Criteria**: Successful local execution of Maps queries and crawler audits via MCP JSON-RPC commands in isolation.

---

## Phase 2: Skill Implementation
*   **Goal**: Translate the declarative skill profiles into runnable agent functions and prompt templates.
*   **Actions**:
    1.  Code the Python prompt templates for all 10 skills in `skills/` (e.g., `seo-audit`, `opportunity-scoring`, `growth-report-generation`).
    2.  Implement standard schema wrappers to marshal inputs and outputs as JSON objects.
    3.  Implement validation helper functions that check output bounds against the schema contracts (e.g., ensuring opportunity classification outputs exactly match one of the 8 approved categories).
*   **Exit Criteria**: All prompt files created and verified using local unit mock inputs.

---

## Phase 3: Agent Implementation
*   **Goal**: Instantiate the 5 agent personas utilizing the Google Agent Development Kit (ADK) Python API.
*   **Actions**:
    1.  Write initialization scripts loading the definitions from `agents/` (e.g., `orchestrator_agent`, `growth_intelligence_agent`).
    2.  Inject system instructions, model parameter bounds (e.g., Gemini 1.5 Pro vs Flash), and output token limits into the ADK instances.
    3.  Bind agents to their designated skills using the authoritative mapping in the manifest.
*   **Exit Criteria**: Agents successfully initialize without runtime configuration exceptions.

---

## Phase 4: Workflow Orchestration
*   **Goal**: Implement the state machine logic that drives the execution DAG.
*   **Actions**:
    1.  Develop the central Orchestrator loop using the state transitions defined in [workflow_routing.yaml](file:///Users/ptech/Desktop/growthscout-ai/workflows/workflow_routing.yaml).
    2.  Code the `LEAD_PARTITIONING` node, ensuring website leads route to crawling and non-website leads skip auditing.
    3.  Implement Orchestrator-only routing governance (blocking peer-to-peer worker calls).
*   **Exit Criteria**: Verification that a mock session transitions through all states matching the routing DAG.

---

## Phase 5: Memory Integration
*   **Goal**: Wire the logical memory domains to active database persistence engines.
*   **Actions**:
    1.  Configure Firestore database connections mapping to the collections defined in [memory_bank_config.yaml](file:///Users/ptech/Desktop/growthscout-ai/memory/memory_bank_config.yaml).
    2.  Enforce domain write ownership checks at the database transaction layer.
    3.  Implement the append-only, immutable constraint for `audit_history` records and version-incrementing rules for `growth_reports`.
    4.  Configure the lifecycle sweep daemon to automatically archive reports and opportunities older than 365 days.
*   **Exit Criteria**: Successful read/write operations enforcing permissions across all 7 canonical domains.

---

## Phase 6: Evaluation Integration
*   **Goal**: Deploy the automated grading framework to safeguard code merges.
*   **Actions**:
    1.  Implement the LLM-as-judge grading prompts in the evaluation configs.
    2.  Configure baseline regression metrics comparison runs.
    3.  Wire local CLI commands (`agents-cli eval run`) to execute over the 5 golden datasets in `eval/datasets/`.
    4.  Integrate the release thresholds gate (safety = 1.00, classification accuracy >= 0.95) into the repository CI/CD pipeline (e.g. GitHub Actions).
*   **Exit Criteria**: CI pipeline automatically executes tests and fails builds on threshold violations.

---

## Phase 7: Security Validation
*   **Goal**: Hard-lock safety boundaries and privacy redactions.
*   **Actions**:
    1.  Implement the PII Redaction Filter using the regex patterns defined in [pii_redaction_rules.json](file:///Users/ptech/Desktop/growthscout-ai/security/pii_redaction_rules.json).
    2.  Implement the Markdown input/output sanitizer utilizing DOMPurify.
    3.  Develop tests asserting that direct prompt injections, tool privilege escalations, and unauthenticated callbacks are blocked and logged.
*   **Exit Criteria**: Security test suite registers 100% blocked-action enforcement on malicious inputs.

---

## Phase 8: Frontend & API Gateway Integration
*   **Goal**: Expose the backend agent runtime to the Next.js presentation layer.
*   **Actions**:
    1.  Implement the FastAPI endpoints (POST `/api/v1/sessions`, GET `/api/v1/sessions/{id}`, POST `/api/v1/sessions/{id}/approve`) matching [api_spec.yaml](file:///Users/ptech/Desktop/growthscout-ai/specs/api_spec.yaml).
    2.  Expose progress event notifications from the Orchestrator over Websocket streams.
    3.  Implement the Next.js UI pages (Discovery Grid, Audit View, Report Approval gate).
*   **Exit Criteria**: API gateway handles mock requests and UI renders report streams successfully.

---

## Phase 9: End-to-End Integration Testing
*   **Goal**: Run verification runs connecting all architectural tiers.
*   **Actions**:
    1.  Deploy the integrated system in a local staging container suite (using docker-compose).
    2.  Execute real-world discovery queries, allowing target crawls to call live sandbox MCP instances.
    3.  Submit reviewer approvals and rejections via the Next.js interface, verifying version increments and feedback persistence.
*   **Exit Criteria**: Successful completion of five end-to-end sessions matching target SMB benchmarks.

---

## Phase 10: Production Readiness Review
*   **Goal**: Freeze configurations and prepare GCP / serverless deployment environments.
*   **Actions**:
    1.  Lock down all Firestore index definitions and security policies.
    2.  Set up production Secrets Management keys in GCP Secret Manager.
    3.  Implement distributed tracing spans (Cloud Trace) across the FastAPI API gateway and individual agents.
    4.  Run final load tests verifying concurrency batches handle up to 5 parallel crawl instances without resource exhaustion.
*   **Exit Criteria**: Platform architecture certified for deployment by the repository governance review board.
