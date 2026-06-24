# Agent Architecture Specification: GrowthScout AI

This document details the multi-agent coordination topology, communication flows, state-sharing mechanisms, and routing rules that govern the 5 agents within GrowthScout AI.

---

## 1. Agent Coordination Topology
GrowthScout AI implements a **Hub-and-Spoke Orchestrator-Worker** pattern. Direct worker-to-worker calls are strictly prohibited to ensure auditability, simple failure boundaries, and predictable routing. Only the Orchestrator may route tasks and execute transitions between agent nodes.

```
                  ┌──────────────────────┐
                  │      User / App      │
                  └──────────┬───────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  Orchestrator Agent  ◄───────────┐
                  └─┬──────┬──────┬──────┬─┘           │ (HITL
                    │      │      │      │             │  Verification)
        ┌───────────┘      │      │      └──────────┐  │
        ▼                  ▼      ▼                 ▼  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│  Discovery    │ │   Analysis    │ │  Opportunity  │ │    Growth     │
│     Agent     │ │     Agent     │ │     Agent     │ │ Intelligence  │
│               │ │               │ │               │ │     Agent     │
└───────────────┘ └───────────────┘ └───────────────┘ └───────────────┘
```

---

## 2. Core Personas & Jurisdictions

All agent boundaries are single-purpose and non-overlapping. Each agent has dedicated responsibilities, inputs, outputs, and allowed capabilities.

### 2.1 Orchestrator Agent (The Director)
*   **Role**: Primary entry point. Parses user instructions, plans task sequences, distributes work to specialist agents, and aggregates results.
*   **Decisions**: Determines whether discovery, audit, or report compilation is required, checks for human authorization logs, and manages the execution flow.
*   **Allowed Skills**: None (routing hub only).
*   **Allowed MCP Tools**: None (enforces security boundary).
*   **Evaluation Responsibilities**: `multi_turn_task_success` >= 0.85, `multi_turn_trajectory_quality` >= 0.90.

### 2.2 Business Discovery Agent (The Finder)
*   **Role**: Specialized local market lookup.
*   **Decisions**: Translates general user queries into precise coordinates and niche terms, discovers target businesses, discovers relevant competitor candidates, classifies website presence statuses, and validates business existence.
*   **Allowed Skills**: `business-discovery`, `local-business-research`.
*   **Allowed MCP Tools**: `local_search_server` -> `local_business_search`.
*   **Evaluation Responsibilities**: `multi_turn_tool_use_quality` >= 0.90, `final_response_quality` >= 0.80.

### 2.3 Website Analysis Agent (The Auditor)
*   **Role**: Technical website presence scanner.
*   **Decisions**: Evaluates page SEO attributes, scrapability constraints (`robots.txt`), CMS characteristics, and loads loading speed logs. Audits target websites and audits competitor websites when requested by the Orchestrator.
*   **Allowed Skills**: `website-analysis`, `seo-audit`.
*   **Allowed MCP Tools**: `web_analyzer_server` -> `web_page_fetcher`, `tech_footprint_scanner`, `seo_auditor`.
*   **Evaluation Responsibilities**: `multi_turn_tool_use_quality` >= 0.90, `hallucination` <= 0.05.

### 2.4 Opportunity Agent (The Strategist)
*   **Role**: Gap analyst and opportunity engine owner.
*   **Decisions**: Reads `competitor_candidates` and `audit_results`, performs comparison audits, generates `competitor_profiles` representing competitive gaps, maps technical errors to business outcomes, computes explainable scoring metrics, and maps opportunities into the 8 formal categories:
    1.  *No Website Opportunity*
    2.  *Website Modernization Opportunity*
    3.  *SEO Opportunity*
    4.  *Performance Opportunity*
    5.  *Conversion Optimization Opportunity*
    6.  *Analytics Opportunity*
    7.  *Reputation Opportunity*
    8.  *Competitive Positioning Opportunity*
*   **Allowed Skills**: `competitor-analysis`, `opportunity-scoring`, `opportunity-classification`, `business-impact-analysis`.
*   **Allowed MCP Tools**: None (runs as a pure reasoning node to protect internal databases from external inputs).
*   **Evaluation Responsibilities**: `final_response_quality` >= 0.85, `hallucination` = 0.00 (must be 100% grounded in crawler outputs).

### 2.5 Growth Intelligence Agent (The Report Compiler)
*   **Role**: Primary Growth Intelligence Report compiler and sales writer.
*   **Decisions**: Formats opportunity scores, gap details, and competitor comparisons into the primary *Growth Intelligence Report*. Synthesizes secondary assets (optional outreach drafts and proposals) derived from report data.
*   **Allowed Skills**: `growth-report-generation`, `outreach-generation`.

*   **Allowed MCP Tools**: None (pure reasoning compiler).
*   **Evaluation Responsibilities**: `final_response_quality` >= 0.88, `hallucination` <= 0.10.

---

## 3. Communication and State Passing Protocol

### Shared Session Context (The Scratchpad)
Agents share context through the ADK State Engine. Instead of dumping raw texts, agents read and write to predefined keys in a shared state dictionary:

```yaml
session_state:
  query_context:
    niche: "plumbing"
    location: "Austin, TX"
  discovery_leads: []              # Populated by Business Discovery Agent
  competitor_candidates: []        # Populated by Business Discovery Agent
  audit_results: {}                # Populated by Website Analysis Agent (includes competitors)
  competitor_profiles: []          # Populated by Opportunity Agent (from competitor comparison)
  opportunity_scores: {}           # Populated by Opportunity Agent (scoring catalog)
  business_impact_analysis: {}     # Populated by Opportunity Agent (gap-to-impact maps)
  growth_reports: {}               # Populated by Growth Intelligence Agent
  hitl_approval_status: {}         # Populated by Orchestrator
```

### Turn Protocol
1.  **Orchestrator invocation**: Takes user prompt -> Writes intent to `query_context`.
2.  **Worker delegation**: Orchestrator invokes `Business Discovery Agent` -> Passes `query_context` -> Discovery writes discovered targets to `discovery_leads` and relevant competitor candidates to `competitor_candidates` -> Returns control.
3.  **Loop execution**: Orchestrator invokes `Website Analysis Agent` sequentially for each target URL and competitor candidate website URL -> Writes all crawling outputs to `audit_results` -> Returns control.
4.  **Inference execution**: Orchestrator invokes `Opportunity Agent` -> Reads `competitor_candidates` and `audit_results` -> Performs comparison and writes findings to `competitor_profiles`, `opportunity_scores`, and `business_impact_analysis` -> Returns control.
5.  **Report compilation**: Orchestrator invokes `Growth Intelligence Agent` -> Reads state opportunity details -> Writes draft Growth Intelligence Report and secondary outputs to `growth_reports`.

---

## 4. Human-in-the-Loop (HITL) Gateways
To ensure security and output quality, the Orchestrator enforces a **HITL Hold** at the following point:
*   **Report Authorization**: The Orchestrator halts execution after `Growth Intelligence Agent` compiles reports. It writes a state-token `awaiting_approval` and sends the payload to the frontend. Only when the user inputs an `approved` callback payload does the Orchestrator mark the task completed.
