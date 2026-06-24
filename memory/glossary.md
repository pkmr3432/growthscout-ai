# Glossary of Terms: GrowthScout AI

This glossary establishes a unified taxonomy and vocabulary for all agents, engineers, and specifications within the GrowthScout AI workspace.

---

## Terminology Catalog

*   **Agent (ADK Agent)**: A specialized, LLM-powered actor defined using the Agent Development Kit (ADK), bounded by specific system instructions, tool configurations, and evaluation metrics.
*   **Awaiting Approval (HITL State)**: An execution state where the Orchestrator halts workflow processing, waiting for a human consultant to review and approve compiled growth reports before completing the task.
*   **Business Profile**: A structured JSON document representing an SMB's metadata, digital presence audit results, identified gaps, and generated outreach collateral. See [business_profile_schema.json](file:///Users/ptech/Desktop/growthscout-ai/memory/business_profile_schema.json).
*   **Digital Presence Audit**: The technical scan performed by the Website Analysis Agent and SEO-audit skill, assessing CMS, meta tags, pixels, and mobile loading speed.
*   **Evaluation-First Development (EFD)**: A software engineering practice where evaluation datasets and judge rubrics are committed to the repository before development of business logic or agent prompts.
*   **Lead Score**: A numeric value between 0 and 100 rating a business lead's conversion potential. Calculated based on detected UX, SEO, and booking widget gaps.
*   **Memory Bank**: The cross-session persistence engine enabling agents to recall past conversation turns, business details, and consultant preferences across different execution runs.
*   **Model Context Protocol (MCP)**: An open-standard interoperability protocol enabling LLM agents to interface with local or remote tool servers (crawlers, search endpoints) via clean JSON-RPC pipelines.
*   **Spec-Driven Development (SDD)**: A software lifecycle paradigm where code is treated as an artifact of specifications. All structural changes begin with editing specs and API definitions.
*   **Trust Boundary**: The interface separating trusted code execution (e.g., ADK orchestrator context) from untrusted external inputs (e.g., website scrapings, user searches).
*   **Workflow Graph (DAG)**: A Directed Acyclic Graph defining the sequence of agent execution turns, tool bindings, and state transitions. See [workflow_routing.yaml](file:///Users/ptech/Desktop/growthscout-ai/workflows/workflow_routing.yaml).
