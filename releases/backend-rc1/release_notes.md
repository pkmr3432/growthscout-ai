# GrowthScout AI — Backend RC1 Release Notes

We are pleased to announce the formal closure of **GrowthScout AI Backend Release Candidate 1 (RC1)**. The backend system is feature-complete, stable, and ready for integration with frontend and API gateway components.

---

## 🚀 Key Highlights

*   **State-Machine Directed DAG Orchestration**: Supports standard, skipped, and alternative execution routes across 11 distinct pipeline states.
*   **Centralized Validation Pipeline**: Secures all workflow state transitions by sequential verification of schemas, business rules, evidence structures, and data normalizations.
*   **Decoupled Model Context Protocol (MCP)**: Features modular tools (`local_business_search`, `web_page_fetcher`, `tech_footprint_scanner`, `seo_auditor`) isolated via stand-alone FastMCP servers.
*   **Agnostic Persistent Memories**: Full composition-factory abstraction enabling seamless switching between `in_memory` and `firestore` checkpoint engines.
*   **Operational Resilience**: Hardened against transient failures, timeouts, network interruptions, and rate limits via circuit breakers (Gemini, Maps, local MCPs, Firestore), retry policy exclusions, and unique `recovery_id` workflow resumptions.

---

## 🛠️ Component Inventory

The certified Backend RC1 consists of:
*   **`orchestrator_agent`**: Prompt instructions, definition files, and code.
*   **`business_discovery_agent`**: Target lead identification prompt instructions and code.
*   **`website_analysis_agent`**: Crawl footprint scanner instructions and code.
*   **`opportunity_agent`**: Urgency & category scoring models.
*   **`growth_intelligence_agent`**: Campaigns and Growth Intelligence Report generator.
*   **`servers/`**: FastMCP search and scraper servers.
*   **`tests/`**: Authoritative suite of 272 automated unit, integration, and security test cases.
*   **`scratch/`**: Smoke test and benchmark runner scripts for automated validation.
