# Project Memory: GrowthScout AI

This file captures the active state, constraints, architecture context, business concepts, and memory governance rules for the GrowthScout AI project workspace. It is designed to preserve repository state across development sessions and provide coding assistants with precise context boundaries.

---

## 1. Project Identity & Purpose

GrowthScout AI is a local digital presence platform designed to convert raw technical details into business intelligence. It is defined as:
*   **Growth Intelligence Platform**: Empowering freelancers, agencies, and consultants to prioritized growth opportunities.
*   **Business Opportunity Discovery Platform**: Translating localized geographic queries into target leads and benchmarked competitor candidates.
*   **Digital Presence Analysis Platform**: Parsing and auditing local SEO, mobile performance, reputation metrics, and conversion tools to identify presence gaps.

## Mission Statement

*   GrowthScout AI exists to help freelancers, consultants, and agencies discover, analyze,  prioritize, and explain business opportunities faster.
*   The platform augments human decision-making rather than replacing consultants.
*   Primary capabilities:
    *   Business Opportunity Discovery
    *   Competitive Intelligence
    *   Opportunity Classification
    *   Opportunity Scoring
    *   Business Impact Analysis
    *   Growth Intelligence Reporting

---

## 2. Active Repository State

*   **Phase**: **Zero-Implementation Specification Phase** (Phase 0/1).
*   **Code Footprint**: Strictly zero application source files. Files present represent configuration specifications (`.yaml`/`.json`) and structural documents (`.md`).
*   **Current Stage**: Architecture Finalization
*   **Remaining Specification Reviews**:
    *   `project_memory.md`
    *   `memory_bank_config.yaml`
    *   `workflow_specification.md`
    *   `workflow_routing.yaml`
    *   `evaluation_specification.md`
    
    *Implementation remains prohibited until specification approval is complete.*

---

## 3. Core Structural Constraints

> [!IMPORTANT]
> Keep the repository strictly modular. Do not consolidate configurations:
> *   Agent configuration prompts must reside only under their respective subdirectory in `agents/`.
> *   Evaluation targets must reside inside `eval/`.
> *   Do not write code blocks in documents that can be parsed as active files (e.g. do not name python snippets as runnable paths).

---

## 4. Core Business Intelligence Concepts

*   **Opportunity Classification**: The automated classification of a business's digital presence gaps into one of the 8 formal categories.
*   **Opportunity Scoring**: The mathematical calculation of a score (0-100) prioritizing identified digital presence gaps using predefined weighted severity heuristics.
*   **Confidence Scoring**: A score (`High`/`Medium`/`Low`) based on evidence completeness (crawler audit completion, competitor comparison, etc.), with mandatory confidence reasoning.
*   **Business Impact Analysis**: Mapping technical audit findings directly to business consequences (e.g., estimating visitor bounce rates or lost conversion opportunities) rather than technical jargon in isolation.
*   **Competitive Intelligence**: Benchmarking a target business's performance (speed, ratings, SEO parameters) against direct local competitor candidates to identify gap differences.
*   **Growth Intelligence Reports**: The primary system output that compiles the summary, findings, benchmarks, opportunity scores, and prioritized recommendations into a master markdown document.

---

## 5. Approved Opportunity Categories

All opportunities discovered must be strictly categorized into one of these 8 approved classes:
1.  **No Website Opportunity**: Business lacks an online domain; focuses on lack of local visibility/trust.
2.  **Website Modernization Opportunity**: Outdated CMS, non-responsive mobile view, missing sitemaps, insecure SSL.
3.  **SEO Opportunity**: Missing meta tags, duplicate headings, missing local schema markup.
4.  **Performance Opportunity**: Page load speed > 5.0 seconds (Core Web Vitals penalties).
5.  **Conversion Optimization Opportunity**: Missing booking widgets, forms, click-to-call.
6.  **Analytics Opportunity**: Missing tag managers, analytics scripts, retargeting pixels.
7.  **Reputation Opportunity**: Low rating (< 4.2), review count < 15, unanswered reviews.
8.  **Competitive Positioning Opportunity**: Competitors dominating local search metrics and presence.

---

## 6. Approved Agent Responsibilities

The system defines 5 specialized, non-overlapping agent personas:
*   **Orchestrator Agent**: Task sequences planning, worker delegation, result aggregation, and HITL gate management. Banned from direct MCP tool execution.
*   **Business Discovery Agent**: Translating queries, local search discovery, competitor candidates lookup, existence validation. Bypasses targets without domains to analyze their online footprint but captures them for "No Website" scoring.
*   **Website Analysis Agent**: Auditing HTML page structures, crawling sitemaps, parsing robots.txt compliance. Audits competitor pages to support benchmarking.
*   **Opportunity Agent**: Performing comparisons, generating competitor profiles, classifying opportunities, calculating opportunity and confidence scores, mapping business impacts. Pure reasoning node (no MCP tool access).
*   **Growth Intelligence Agent**: Formats scoring and impact analyses into the master Growth Intelligence Report. Synthesizes secondary outreach copy/proposals. Pure reasoning node (no MCP tool access).

---

## 7. Approved Skill Ownership Matrix

This matrix acts as the single source of truth for agent-to-skill bindings:

| Agent | Skills |
| --- | --- |
| Business Discovery Agent | `business-discovery`, `local-business-research` |
| Website Analysis Agent | `website-analysis`, `seo-audit` |
| Opportunity Agent | `competitor-analysis`, `opportunity-classification`, `opportunity-scoring`, `business-impact-analysis` |
| Growth Intelligence Agent | `growth-report-generation`, `outreach-generation` |
| Orchestrator Agent | No direct skills; routing and workflow management only |

---

## 8. Key Approved Decisions

*   **Hub-and-Spoke Topology**: No peer-to-peer agent communications to isolate failure boundaries and maintain auditability.
*   **Zero-Implementation Constraint**: Strict prohibition of runnable code files (Python, JavaScript, Next.js components) during Phase 0 to ensure spec-driven design.
*   **Grounded Decisions Over Assumptions**: Outbound recommendations and opportunity scores must cite direct tool outputs rather than LLM assumptions.
*   **Human-in-the-Loop Gateways**: Enforce mandatory human approval checkpoints before finalizing/delivering reports, proposals, or outreach copy.
*   **Evaluation-First Development**: Agent prompts, flows, and skills must validate against `evaluation_cases.json` via the grading framework before deployment.
*   **Primary Product Output**: The *Growth Intelligence Report* is the primary system output. Outreach messages and proposal drafts are secondary artifacts derived from the Growth Intelligence Report.

---

## 9. Memory Governance Summary

*   **Session Memory**: Short-term, ephemeral state (e.g. chat logs, query contexts, intermediate crawler results). Retained for a maximum of 90 days.
*   **Business Profiles**: Persistent Firestore storage containing basic business profile metadata (name, address, verified presence tags, etc.).
*   **Opportunity History**: Historical logs of classified opportunities and scores generated for audited local businesses to track progress.
*   **Competitor Snapshots**: Frozen audit benchmarks of direct local competitors captured at the time of target business auditing.
*   **Human Notes**: Custom user overrides, corrections, and manual notes entered during HITL checkpoints.
*   **PII Handling**: Automated sanitization/redaction boundary filters that strip out phone numbers, emails, and address variants before third-party LLM calls are processed.
*   **Growth Intelligence Reports**: Persistent historical reports generated for audited businesses and retained for future comparison and benchmarking.
