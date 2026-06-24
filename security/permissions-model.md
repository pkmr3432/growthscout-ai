# Permissions Model: GrowthScout AI

This model defines the execution privileges, model access levels, and tool access controls for all agents inside GrowthScout AI.

---

## 1. Agent-to-Tool Access Matrix
Agents are barred from executing unmapped tools. Access is controlled by the following matrix:

| Tool Name | Discovery Agent | Analysis Agent | Opportunity Agent | Growth Intelligence Agent | Orchestrator Agent |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `local_business_search` | **Granted** | Denied | Denied | Denied | Denied |
| `web_page_fetcher` | Denied | **Granted** | Denied | Denied | Denied |
| `tech_footprint_scanner` | Denied | **Granted** | Denied | Denied | Denied |
| `seo_auditor` | Denied | **Granted** | Denied | Denied | Denied |

---

## 2. API Scope Configuration
*   **Google Maps Access**: The `local_business_search` tool can only perform read-only lookups (Places Search, Details API). It is blocked from calling write-endpoints (Maps Business Profile management).
*   **Database Writes**: Only the Orchestrator Agent (via the FastAPI backend identity) has permission to write session states to Firestore. All worker agents have read-only access to their specifically delegated session input payloads.
*   **Model Execution Scopes**: FLASH models execute with a standard 1,000 output tokens limit. PRO models are granted a maximum of 4,000 output tokens for report and outreach synthesis.
