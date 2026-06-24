# Architecture Decisions Catalog: GrowthScout AI

This catalog tracks the core design patterns, structural choices, and technology trade-offs established for the GrowthScout AI platform.

---

## 1. Architectural Decisions Summary Table

| Reference | Decision | Status | Rationale |
| :--- | :--- | :--- | :--- |
| **GSAD-001** | **Monorepo Directory Layout** | Approved | Keeps frontend, backend, agent definitions, and MCP servers in a single repository for simplified CI/CD, dependency coordination, and schema sharing. |
| **GSAD-002** | **Hub-and-Spoke Agent Coordination** | Approved | Simplifies debugging and ensures audit logging. Prevents runaway agent loops by forcing all worker delegations to route through the central Orchestrator. |
| **GSAD-003** | **Vertex AI Agent Runtime Deployment**| Approved | Out-of-the-box support for session management, Vertex AI Cloud Trace, and Google Cloud IAM bindings. |
| **GSAD-004** | **Model Context Protocol (MCP) Integration**| Approved | Decouples direct API interactions from agent prompts, allowing tools to be run in sandboxed environments without bloating LLM context. |
| **GSAD-005** | **Memory Bank & Profile Isolation** | Approved | Separates ephemeral session history from persistent SMB knowledge base records, preventing prompt context bloat during multi-turn chats. |
| **GSAD-006** | **In-Transit PII Masking** | Approved | Blocks transmission of private lead email addresses and phone numbers to external LLMs, ensuring enterprise-grade compliance. |

---

## 2. In-Depth Decision Logs
*For detailed execution logs, rationales, alternatives considered, and impact analyses, see the Architecture Decision Records (ADRs) located at [docs/adr/](file:///Users/ptech/Desktop/growthscout-ai/docs/adr/).*
