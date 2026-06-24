# System Architecture Specification: GrowthScout AI

This document defines the high-level system architecture, service layers, component boundaries, and data flow guidelines for the GrowthScout AI platform.

---

## 1. Logical Architecture

The platform architecture is structured into independent layers to enforce the separation of concerns, scalability, and security boundaries.

```
       ┌────────────────────────────────────────────────────────┐
       │                   Presentation Layer                   │
       │           User Interface & Client Audit View           │
       └───────────────────────────┬────────────────────────────┘
                                   │ HTTPS / WebSockets / JSON
                                   ▼
       ┌────────────────────────────────────────────────────────┐
       │                   Application Layer                    │
       │          FastAPI Gateway, Routing, HITL Gates          │
       └───────────────────────────┬────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                             Agent Layer                              │
│              Role Personas & Orchestration workflow DAG              │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                             Skill Layer                              │
│             Modular, Reusable Competences & Capabilities             │
└──────────────────┬─────────────────────────────────┬─────────────────┘
                   │                                 │
                   ▼ (MCP JSON-RPC)                  ▼ (Logic / Prompts)
┌─────────────────────────────────────┐   ┌────────────────────────────┐
│        MCP Integration Layer        │   │ Opportunity Intel Layer    │
│  External Search & Crawler Servers  │   │ Scoring, Classification &  │
│                                     │   │ Growth Report Synthesis    │
└─────────────────────────────────────┘   └────────────────────────────┘
  
   ==================================================================
   CROSS-CUTTING CONCERNS:
   * Security Layer: Input Validation -> PII Redaction -> Tool Scopes
   * Evaluation Layer: Agent -> Skill -> Workflow -> System grading
   ==================================================================
```

### 1.1 Presentation Layer
*   **Responsibilities**: Provides a responsive workspace for the user (consultant). Renders local lead discovery grids, website audit results, and compile-ready Growth Intelligence Reports. Handles the Human-in-the-Loop review and approval gates.
*   **Interactions**: Communicates with the Application Layer using REST APIs for configuration and WebSockets for real-time task progress streams.

### 1.2 Application Layer
*   **Responsibilities**: Serves as the API Gateway. Orchestrates requests, manages database sessions, implements rate limiting, and serves as the Client Host for MCP tool sessions.
*   **Interactions**: Intercepts requests, validates authorization tokens, routes payloads to the Agent Layer, and exposes HITL callbacks.

### 1.3 Agent Layer
*   **Responsibilities**: Manages agent personas, routing logs, and task execution graphs. Coordinates workers (Discovery, website analysis, opportunity, and Growth Intelligence) through a central Orchestrator Hub.
*   **Interactions**: Binds user intent parameters into state contexts and delegates tasks to target skills based on the active workflow DAG.

### 1.4 Skill Layer
*   **Responsibilities**: Defines reusable capability packages (e.g. `seo-audit`, `opportunity-scoring`, `outreach-generation`) that agents bind to dynamically. Skills act as the interface between the Agent's reasoning and tool invocation.

*   **Interactions**: Orchestrated by agents. Binds input parameters, executes reasoning templates, and invokes MCP tools.

### 1.5 MCP Integration Layer
*   **Responsibilities**: Decouples API client libraries and credentials from the agent prompts. Hosts local or remote tool servers (Maps search, crawler instances).
*   **Interactions**: Communicates via standard Model Context Protocol JSON-RPC. Resolves schemas and enforces tool contracts.

### 1.6 Memory Layer
*   **Responsibilities**: Manages session histories, target business profiles, knowledge bases, and vector retrieval indices.
*   **Interactions**: Accessed by the Application Layer for state persistence and by the Agent Layer for long-term recall.

### 1.7 Opportunity Intelligence Layer
*   **Responsibilities**: Classifies detected web gaps into the 8 formal Opportunity Categories. Computes transparent, explainable Opportunity Scores, maps technical errors to business impacts, and coordinates the compilation of the primary Growth Intelligence Report.
*   **Interactions**: Reads crawler audit outputs from the Skill Layer, performs scoring reasoning, and delivers structured reports to the Growth Intelligence Agent.

### 1.8 Evaluation Layer
*   **Responsibilities**: Operates as a first-class architectural concern. Automates grading pipelines for agents, skills, workflows, and end-to-end system outputs. Enforces regression testing against golden datasets during CI.
*   **Interactions**: Monitors execution traces generated by the Agent/Skill layers and grades them using LLM-as-judge rubrics and Code Execution metrics.

### 1.9 Security Layer
*   **Responsibilities**: Cross-cutting safety interceptor. Enforces input validation, sanitizes inputs for prompt injections, redacts PII data at trust boundaries, and audits tool execution permissions.
*   **Interactions**: Wraps Gateway routes and intercepts outgoing LLM calls and tool execution pipelines.

---

## 2. Deployment Architecture

The platform architecture is vendor-neutral, ensuring that core modules can be compiled and hosted across multiple containerized or serverless environments.

### 2.1 Deployment Requirements
*   **Microservices Runtime**: Requires an environment capable of running containerized backend gateway applications and MCP tool daemons.
*   **Agent Execution Engine**: Requires a managed agent execution runtime supporting session management and trace logs.
*   **Secret Manager Access**: Enforces secure IAM-bound access to third-party maps and proxy API keys.
*   **Trace Observability**: Requires distributed trace logging tracking execution steps across the API gateway, orchestrator, and individual MCP tools.

### 2.2 Deployment Options (Replaceable)
*   **Option A (Google Cloud Platform)**: Deploy the FastAPI Gateway and MCP Servers to Google Cloud Run, execute agents on Vertex AI Agent Runtime, store profiles in Firestore, and run analytics via BigQuery.
*   **Option B (Standard Container Orchestration)**: Deploy the gateway and MCP servers to a Kubernetes (EKS/GKE) cluster, execute agents in containerized ADK Python runtime pods, use Redis for session management, and PostgreSQL for profile persistence.

---

## 3. Expanded Memory Architecture

Memory is decoupled into four segregated subsystems to optimize context lengths and protect privacy:

| Memory Tier | Responsibility | Target Storage Type | Retention Policy |
| :--- | :--- | :--- | :--- |
| **Session Memory** | Tracks ephemeral multi-turn chat logs and active workflow state tokens for a single user query. | Ephemeral Session Store (Redis / In-Memory cache) | Purged 90 days after session inactivity. |
| **Business Profile Memory** | Stores audited SMB details, technical findings, competitor comparisons, and reports. | Persistent Business Profile Store (Firestore / PostgreSQL) | Indefinite (Acts as historical profile database). |
| **Project Knowledge Memory** | Recalls high-level consultant preferences, style guides, pricing templates, and blacklists. | Vector Retrieval Layer (Vector DB / Vector Index) | Indefinite. |
| **Evaluation Memory** | Stores historical evaluation traces, regression results, and LLM-judge outputs. | Agent Analytics Store (BigQuery / Data Lake) | Indefinite (Used for offline Quality Flywheel analysis). |

---

## 4. Core System Data Flow

The canonical execution flow traverses the system layers sequentially, enforcing Human-in-the-Loop gates:

```
[User Query] ──> [Business Discovery] ──> [Website Analysis] ──> [Competitive Analysis]
                                                                          │
[Human Review] ◄── [Growth Intelligence Report] ◄── [Scoring] ◄── [Opportunity Intel]
```

1.  **User Query**: User submits niche + location parameters to the Gateway.
2.  **Business Discovery**: Discovery Agent searches maps MCP server, classifying businesses into No Website, Outdated Website, or Modern Website.
3.  **Website Analysis**: Scraper MCP audits page metadata, speed, and widget presence for target leads with websites.
4.  **Competitive Analysis**: Opportunity Agent queries maps to gather competitors and benchmark rating performance.
5.  **Opportunity Intelligence**: Gaps are mapped to the 8 Opportunity Categories (e.g. SEO, Conversion, Performance).
6.  **Opportunity Scoring**: Transparent, explainable scores are compiled, citing verified evidence.
7.  **Growth Intelligence Report**: Findings are compiled into a master Markdown report. Proposals are generated as secondary outputs.
8.  **Human Review**: Execution halts at the HITL Gateway, awaiting approval.

---

## 5. Architecture Validation Checklist

Before implementation begins, developers must verify that the codebase design conforms to this checklist:

*   **Constitution Compliance**: Zero application code is written during Phase 0; all specifications are finalized.
*   **PRD Alignment**: The primary product output is the Growth Intelligence Report; outreach copy is a secondary derived output.
*   **Agent/Skill Separation**: Agents only orchestrate workflows; specific logic resides inside reusable Skill directories.
*   **MCP Interoperability**: All external tools run via MCP tool contracts without hardcoding credentials inside agent prompts.
*   **Evaluation-First**: Metrics config (`eval_config.yaml`) and datasets are established and runnable via `agents-cli eval run`.
*   **Security-First**: PII redaction filters and input sanitization regex check blocks are active on the gateway boundary.
*   **HITL Support**: Human checkpoints halt the orchestrator, and rejections route feedback back to proposal compilation.
*   **Vendor Neutrality**: The system design contains no hardcoded dependencies on proprietary cloud providers.
