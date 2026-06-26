# GrowthScout AI: Business Discovery & Growth Intelligence Platform

Welcome to the **GrowthScout AI** repository. GrowthScout AI is a production-grade AI agent platform designed to help freelancers, agencies, and consultants identify local business growth opportunities, analyze SMB digital footprints, run automated SEO and stack audits, and construct bespoke growth marketing campaigns and Growth Intelligence Reports.

As of **June 26, 2026**, the backend implementation of GrowthScout AI is **feature-complete and Release Candidate 1 (RC1) certified**. The platform leverages the Google Agent Development Kit (ADK) and Model Context Protocol (MCP) to run domain-specific agents coordinated by a centralized, stateful orchestrator.

---

## 📂 Repository Directory Layout

The repository is organized into distinct domain-driven folders:

```
├── README.md                      # Onboarding and repository guidelines
├── PROJECT_CONSTITUTION.md        # Governance laws and code style guidelines
├── specs/                         # Core product, system, and agent specifications
├── memory/                        # Session/Profile schemas & Memory Bank configuration
├── docs/                          # Developer guides, playbooks, and ADRs
├── agents/                        # Personas, prompts, and code for all 5 platform agents
│   └── orchestrator_agent/        # Core orchestrator state machine, validators, & config
├── servers/                       # MCP server implementations (local search, web analyzer)
├── workflows/                     # DAG routing maps and YAML topologies
├── tests/                         # Full automated test suite (agent, contract, integration, orchestrator, security)
├── scratch/                       # Verification runner scripts, datasets, and reports
└── releases/                      # Release snapshots and changelogs
    └── backend-rc1/               # Finalized Backend RC1 release closure snapshot
```

---

## 🌟 Core System Features

*   **Multi-Agent Coordination**: Led by the `orchestrator_agent` executing a state machine with 11 distinct workflow states (e.g. `DISCOVERING`, `LEAD_PARTITIONING`, `AUDITING`, `OPPORTUNITY_ANALYSIS`, `REPORT_GENERATION`, `AWAITING_APPROVAL`).
*   **Centralized Validation Pipeline**: Enforces validation sequentially (Schema -> Business Rules -> Evidence -> Normalization) before committing any state transitions.
*   **Model Context Protocol (MCP)**: Decoupled API tools (`local_business_search`, `web_page_fetcher`, `tech_footprint_scanner`, `seo_auditor`) provided by isolated FastMCP servers.
*   **Persistent Checkpoints**: Backend-agnostic persistence supporting memory-based (`in_memory`) and database-based (`firestore`) saving and loading.
*   **Operational Resilience**: Built-in timeout enforcement, circuit breakers with transition callbacks for dependencies (Gemini, Google Maps, local MCPs, Firestore), exponential backoff retries (validation errors bypass retries and fail fast), and traceable workflow recovery (generating a unique `recovery_id` prefix).

---

## 🚀 Getting Started & Verification

Ensure you have Python 3.10+ installed. Install dependencies inside a virtual environment.

### 1. Environment Configuration
Create a `.env` file in the root directory (refer to [.env.example](file:///Users/ptech/Desktop/growthscout-ai/.env.example) for variables):
```bash
cp .env.example .env
# Edit .env and supply your GEMINI_API_KEY and GOOGLE_MAPS_API_KEY
```

### 2. Execute Automated Regression Tests
Run the authoritative test suite (272 collected test cases, verifying 13 core state scenarios, resilience logic, security boundaries, and schema converters):
```bash
PYTHONPATH=. pytest
```
*Expected output: `271 passed, 1 skipped` (the live integration test is skipped if keys are not supplied).*

### 3. Run Live Preflight Smoke Tests
Verify configuration, live MCP subprocess communications, scraper networks, and agent registry mappings:
```bash
PYTHONPATH=. python3 scratch/run_smoke_test.py
```

### 4. Execute End-to-End Benchmark Workflows
Run simulated business cases (`hvac_austin` standard flow with checkpoint resume, `plumbing_seattle` website bypass, and `dentistry_chicago` isolated crawler failures):
```bash
python3 scratch/run_benchmarks.py
```
Outputs are written to [benchmark_results.json](file:///Users/ptech/Desktop/growthscout-ai/scratch/benchmark_results.json).

---

## 🛡️ Release and Security Policies

*   **Article III Rule**: Backend architecture is under feature freeze. No new API endpoints or topological changes may be committed.
*   **Explainability**: All opportunity scores and campaigns must cite tool-generated evidence rather than opaque assumptions.
*   **Security Sandboxing**: No agent may execute unsanitized commands in a host OS terminal. PII is redacted at the gateway boundary.
