# Model Context Protocol (MCP) Architecture: GrowthScout AI

This document specifies the Model Context Protocol (MCP) integration topology, security boundaries, tool governance, authentication models, failure recovery, and observability protocols for GrowthScout AI.

---

## 1. MCP Philosophy

Model Context Protocol (MCP) is the core integration standard that decouples raw tool execution from LLM prompt logic. 
*   **Sandbox Isolation**: Agents must never run raw API code, shell scripts, or system-level network requests. All tool executions are offloaded to sandboxed MCP servers running as separate processes.
*   **Declarative Tool Contracts**: Agents invoke tools via declarative JSON-RPC messages specifying tool schemas. The MCP gateway validates arguments and filters inputs before tool execution.

---

## 2. Server and Trust Boundaries

GrowthScout AI operates under a strict trust boundary model separating trusted reasoning runtimes from untrusted external data crawlers:

```
                  ┌──────────────────────┐
                  │ Core Agent Runtime   │ (Trusted Domain)
                  │ (Gemini / ADK Engine)│
                  └──────────┬───────────┘
                             │
     ========================┼======================== [Trust Boundary Gate]
                             │ (JSON-RPC over stdin/stdout or SSE)
                             ▼
                  ┌──────────────────────┐
                  │    MCP Client / App  │ (Trusted Host Process)
                  └────┬────────────┬────┘
                       │            │
         ┌─────────────┘            └─────────────┐
         ▼                                        ▼
  ┌──────────────┐                         ┌──────────────┐
  │ Local Search │ (Sandbox Domain)        │ Web Analyzer │ (Sandbox Domain)
  │  MCP Server  │                         │  MCP Server  │
  └──────┬───────┘                         └──────┬───────┘
         │                                        │
         ▼ (Google Maps API)                      ▼ (Untrusted Web Scrapes)
  [Google Maps Places]                     [Target SMB Websites]
```

*   **Trusted Domain**: The Core Agent Runtime and the MCP Client (FastAPI host) are fully trusted. They manage database connections, session variables, and encryption keys.
*   **Sandbox Domain**: MCP servers run in isolated sandbox boundaries (e.g., containerized runtimes with no access to local files or internal database endpoints). They only execute specific, registered tools.
*   **Untrusted Web Scrapes**: Scraped HTML content and target page metadata are treated as untrusted payloads. They must pass through sanitization gates before entering the trusted agent layer.

---

## 3. MCP Tool Governance

Every tool exposed via MCP is governed by a formal schema and contract:
*   **Contract Ownership**: The schema files in `mcp/schemas/` and API contracts in `mcp/contracts/` are the authoritative schemas for tool execution. No tool can be executed if its inputs or outputs violate these schema contracts.
*   **Least Privilege Allocation**: Agents are only allowed to access specific tools registered in `agents-cli-manifest.yaml`. Any attempt by an agent to request an unregistered tool is blocked by the MCP client.

---

## 4. Authentication and Authorization Model

The MCP architecture enforces secure authentication and authorization:
*   **Host-to-Server Authentication**: Servers running locally communicate with the client via standard input/output (`stdin`/`stdout`) pipes. In distributed deployments, remote MCP servers authenticate to the client gateway using secure Server-Sent Events (SSE) wrapped in Mutual TLS (mTLS) with token authentication.
*   **API Key Management**: MCP servers do not fetch secrets directly. The trusted MCP Client injects authorized API keys (e.g., Maps API keys) into the server environment at startup.
*   **Authorization Matrix**: Tool execution is authorized based on the caller agent's identity:
    *   `business_discovery_agent` $\rightarrow$ Authorized for `local_business_search`.
    *   `website_analysis_agent` $\rightarrow$ Authorized for `web_page_fetcher`, `tech_footprint_scanner`, `seo_auditor`.
    *   `opportunity_agent`, `growth_intelligence_agent`, and `orchestrator_agent` $\rightarrow$ **Blocked** from all direct tool execution.

---

## 5. Schema and Contract Management

*   **Schema Schema Definitions**: All MCP tools must expose their schemas in standard JSON Schema Draft-07 format.
*   **Contract Upgrades**: Any upgrade to tool inputs or outputs must follow a backward-compatible versioning policy. Breaking changes in tool structures require incrementing the MCP interface contract version (e.g., `web_analyzer_contract.yaml` v1.0.0 $\rightarrow$ v2.0.0).

---

## 6. Security Controls & Sanitization

To protect the Agent Layer from prompt injection and script execution:
*   **HTML Sanitization**: The `web_page_fetcher` tool must strip out all script tags (`<script>`), iframe objects (`<iframe>`), inline stylesheets, and unneeded markup attributes before returning text.
*   **PII Redaction Gate**: Raw crawler logs are passed through a PII Redaction Filter to mask emails, phone numbers, and IP addresses before the text is written to the `audit_history` memory domain.
*   **Parameter Sanitization**: Input parameters for `local_business_search` are checked for shell command control characters to prevent command injections.

---

## 7. Failure Handling and Resilience

MCP operations are designed to fail gracefully without crashing the parent session:
*   **Graceful Degradation**: If an MCP tool returns an error (e.g., HTTP 403, DNS timeout, scraping block), the server returns a structured error object (e.g., `{"success": false, "reason": "timeout"}`) instead of exiting.
*   **Timeout Policy**: Tool invocations are capped at **15 seconds** per request. If a scraper fails to respond within this limit, the client terminates the connection, logs a `tool_timeout` event, and continues the workflow with empty/partial logs.
*   **Rate-Limit Controls**: The client regulates crawl requests through queue batching (concurrency limited to 5 domains) to avoid trigger locks.

---

## 8. Observability & Distributed Tracing

Every tool invocation must be fully observable:
*   **Trace Identifiers**: Every JSON-RPC request emitted by the client includes a unique `correlation_id` and `session_id`.
*   **Log Forwarding**: MCP server process stderr logs are captured by the client and forwarded to the central Logging Service.
*   **Performance Metrics**: The client tracks execution time, memory utilization, and failure rates for every tool called, feeding these metrics into evaluation loops.

---

## 9. Interoperability Requirements

*   **Standard Compliance**: All servers must adhere strictly to the Model Context Protocol Specification version `0.1.0` or higher.
*   **Transport Layer**: Stdin/stdout transport is the default for local process runtimes. SSE HTTP transport is the default for remote service integrations.
