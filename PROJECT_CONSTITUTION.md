# GrowthScout AI: Project Constitution

This Constitution defines the immutable governance, architectural principles, and collaboration laws for the **GrowthScout AI** project. All developers, maintainers, and agentic assistants (including coding LLMs) working in this workspace must adhere to these directives.

---

## Article I: Mission and Purpose

1.  **Core Mission**: GrowthScout AI is dedicated to providing transparent, accurate, and actionable growth intelligence to freelancers, agencies, and consultants. The platform's ultimate purpose is to empower service providers with data-driven insights that help local businesses thrive in the digital economy.
2.  **Factual Integrity**: The platform must prioritize precision and truthfulness. Gaps and opportunities must be backed by verifiable data extracted via tools, rather than LLM inference assumptions or heuristics unsupported by evidence.
3.  **Non-Goals**: GrowthScout AI is explicitly NOT:
    *   A generic chatbot for raw conversational interactions.
    *   A fully autonomous sales agent executing transactions without oversight.
    *   An email spam or mass outreach distribution platform.
    *   A replacement for human consultants, agencies, or business advisors.
    The platform exists solely to augment human decision-making through targeted business intelligence, technical presence analysis, and personalized recommendations.
4.  **Business Impact Principle**: GrowthScout AI must prioritize business outcomes over technical findings in isolation. Website audits, SEO findings, performance metrics, accessibility issues, and technology analysis should always be connected to measurable business impact whenever possible. Agents must focus on identifying:
    *   *Lost opportunities* (e.g., bounced traffic from slow page loads).
    *   *Growth opportunities* (e.g., capturing nearby search queries via Schema).
    *   *Customer acquisition opportunities* (e.g., scheduling widgets to convert visits).
    *   *Revenue-related opportunities*.
    *   *Competitive weaknesses*.
    Rather than reporting technical issues in isolation, agents must translate findings into outcomes that influence lead conversion, customer retention, or brand positioning.
5.  **Explainability and Evidence Principle**: All opportunity scores, recommendations, lead scores, growth assessments, and business insights must include supporting reasoning. The system must prefer transparent reasoning over opaque, black-box scoring. Agents must:
    *   Cite the specific tool outputs that influenced the decision or score.
    *   Explain the business logic of why a recommendation was generated.
    *   Distinguish verified findings (grounded in tool executions) from assumptions.
    *   Explicitly communicate uncertainty when evidence is incomplete or tool responses fail.

---

## Article II: Spec-Driven Development (SDD)

1.  **Specification Primacy**: No implementation code (Python, TypeScript, SQL, or other) may be committed to this repository unless a corresponding specification, schema, or evaluation dataset exists in the `specs/`, `memory/`, `mcp/`, or `eval/` directories.
2.  **No Configuration Mismatch**: The implementation code must match the manifests in `agents-cli-manifest.yaml` and the schemas in `memory/` exactly. Any API route parameter or agent state modification must start with a PR (Pull Request) changing the specifications first.
3.  **Strict Schema Compliance**: JSON payloads exchanged between backend routes, Next.js frontend pages, and MCP tool servers must validate against their defined schemas at run time.

---

## Article III: Backend Implementation & Release Candidate 1 Laws

1.  **Implementation Transition**: The project has transitioned from the "Zero-Implementation" specification phase to an "Implemented and RC1 Certified" backend state. Source code and tests are now active in the repository.
2.  **Feature Freeze**: The backend architecture and functionality are strictly frozen as of Release Candidate 1. No new features, API routes, or state machine transitions may be introduced without first updating the corresponding specifications and getting explicit maintainer approval.
3.  **Stability Preservation**: All modifications must focus exclusively on bug fixes, performance optimization, security hardening, and documentation updates. Full backward compatibility with the existing offline test suite and benchmark suite must be preserved.

---

## Article IV: Agentic Engineering and Skill Reusability

1.  **Multi-Agent Role Separation**:
    *   Agents must remain single-purpose. They are barred from overlapping functional jurisdictions (e.g., the `website_analysis_agent` must analyze web footprints; it cannot suggest growth pricing campaigns, which is the jurisdiction of the `opportunity_agent`).
    *   The `orchestrator_agent` is the sole routing coordinator. Sub-agents do not spawn other sub-agents directly; routing occurs dynamically or via the orchestrator using workflows described in `workflows/workflow_routing.yaml`.
2.  **Skill Independence**:
    *   Skills are self-contained logical blocks. A skill package (e.g., `seo-audit`) must be capable of execution on any agent that meets its tool requirements.
    *   Every skill package must document its inputs, outputs, and include dummy traces in `examples.md` to demonstrate target behavior.

---

## Article V: Model Context Protocol (MCP) and Tool Usage

1.  **Protocol Adherence**: All external tool interactions must run through standardized Model Context Protocol (MCP) channels. Tool client-server data exchanges must validate against tool schemas in `mcp/schemas/`.
2.  **Grounded Decisions over Assumptions**: Agents must base all analysis, gap detections, and marketing recommendations on verified tool output results. Hallucinating or assuming website performance parameters, missing scripts, or business details without tool verification is strictly prohibited. If tool data is unavailable, the agent must report the gap as unverified.

---

## Article VI: Memory Governance

1.  **State Segregation**: Ephemeral session memory (chat logs, task-specific states) and persistent business profiles must remain decoupled. Epic context states must not bloat agent interaction prompts.
2.  **PII Sanitization**: Personal Identifiable Information (PII) must be redacted at the gateway boundary. No unmasked email addresses, phone numbers, or private user IDs may be saved in long-term profiles or passed to external LLM services.
3.  **Data Minimization**: Retention limits must be enforced on ephemeral states. Session logs must expire and be purged after the defined retention period (90 days).

---

## Article VII: Human-in-the-Loop (HITL) Checkpoints

1.  **Non-Bypassable Review Gates**: Automated systems are prohibited from executing outbound marketing outreach or finalizing Growth Intelligence Report PDFs without a human review checkpoint.
2.  **Feedback Iteration**: If a report draft is rejected by the human reviewer, the workflow engine must capture the human feedback and route execution back to the respective generation agent for corrective iteration.
3.  **Human Supremacy**: The human user holds final authority to modify, override, or discard any agent-generated suggestion, gap analysis, or pricing recommendation.

---

## Article VIII: Evaluation-First Quality Control

1.  **The Quality Flywheel Standard**:
    *   Every agent must achieve a minimum evaluation score before it can be merged into the `main` deployment branch.
    *   Tests that validate LLM output persona, style, or response text are strictly forbidden in standard unit test suites (e.g., `pytest`). Such behaviors must be evaluated via the Agent Platform Evaluation Service using LLM-as-judge rubrics.
2.  **Baseline Regressions**:
    *   No change shall be approved if it causes a decrease in `multi_turn_task_success` or `multi_turn_tool_use_quality` across standard datasets.

---

## Article IX: Security & Safety Guardrails

1.  **PII Redaction**: All customer-facing text and third-party data inputs must pass through PII redaction filter check rules before being forwarded to LLM endpoints.
2.  **Tool Sandboxing**: Any tool that executes commands or downloads assets must operate in a restricted environment. Under no circumstances may an agent execute unsanitized strings in a host OS terminal.
3.  **Access Control**: Agents must only execute tools that are explicitly declared in their `definition.yaml`. Unregistered tool invocations must be denied, logged as a security exception, and flagged for human review.
