# ADR-002: Multi-Agent Hub-and-Spoke Topology

## Status
Approved

## Context
GrowthScout AI executes multiple complex tasks: local search, web crawling, tech footprint scraping, gap evaluation, and marketing copy generation. Placing all of these instructions into a single LLM prompt leads to context dilution, tool selection errors, and poor proposal quality.

We need a multi-agent orchestration strategy that remains manageable, verifiable, and trace-friendly.

## Decisions
1.  **Orchestrator-Worker Pattern**: We establish a central `Orchestrator Agent` that acts as the hub. Sub-agents (Discovery, Analysis, Opportunity, and Growth Intelligence) do not communicate directly.
2.  **Explicit Routing (DAG)**: The Orchestrator routes execution based on a Directed Acyclic Graph (DAG) specified in `workflows/workflow_routing.yaml`.
3.  **Model Allocation**:
    *   `Gemini 1.5 Pro` is allocated to the `Orchestrator` (for planning) and `Growth Intelligence Agent` (for long-context report compilation and outreach synthesis).
    *   `Gemini 1.5 Flash` is allocated to `Business Discovery`, `Website Analysis`, and `Opportunity` agents to minimize latency and hosting costs.

## Consequences
*   **Positives**: Personas are highly isolated and easy to unit-test. Prompt lengths are kept short, improving response accuracy.
*   **Negatives**: State must be explicitly shared between turns, adding overhead.
*   **Mitigations**: We use a unified session database schema (`session_memory_schema.json`) to act as a shared scratchpad, managed by the Orchestrator.
