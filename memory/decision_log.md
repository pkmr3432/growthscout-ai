# Technical Decision Log: GrowthScout AI

This file documents the chronological sequence of architectural, design, and structural decisions made during the lifecycle of the GrowthScout AI project.

---

## Chronological Log

### [2026-06-24] Initial Platform Foundation Setup
*   **Action**: Created repository specifications, governance models, evaluation datasets, and folder directories.
*   **Decisions**:
    1.  Established a pure zero-implementation workspace (no Python, TypeScript, or script files) to enforce Spec-Driven Development rules.
    2.  Standardized on Python FastAPI for the API Gateway and Next.js for the UI.
    3.  Bound agent definitions to YAML blueprints containing explicit input, output, tools, and evaluation parameters.
    4.  Adopted Google Agent Development Kit (ADK) and Model Context Protocol (MCP) as core integration protocols.
    5.  Approved the multi-agent schema consisting of five specialized personas: Orchestrator, Discovery, Website Analysis, Opportunity, and Growth Intelligence.
*   **Outcome**: Ready for development team review and hand-off.

### [2026-06-24] Evaluation Framework Hardening
*   **Action**: Configured metrics in `eval/eval_config.yaml` and set pass/fail thresholds.
*   **Decisions**:
    1.  Set safety evaluation gate to 1.0 (strict block on prompt injections).
    2.  Set task success gate to >= 0.85 and hallucination gate to <= 0.10.
    3.  Decided to isolate LLM-as-judge criteria from standard unit testing files, reserving pytest only for code syntax and structural integrity check.
*   **Outcome**: The Quality Flywheel testing harness is ready to audit future code implementations.
