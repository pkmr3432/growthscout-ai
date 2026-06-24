# MCP Integration Specification: GrowthScout AI

This document defines the interface standards, JSON-RPC communication transport, connection lifecycle, and exception handling protocols for Model Context Protocol (MCP) servers within the GrowthScout AI ecosystem.

---

## 1. Connection Transport Architecture
To allow agents to communicate with external APIs, the platform uses two MCP transport channels:
1.  **Stdio Transport (Local Development)**: The FastAPI daemon spawns the MCP servers as sub-processes, exchanging JSON-RPC payloads over stdin/stdout channels.
2.  **SSE (Server-Sent Events) Transport (Production)**: MCP servers run as independent Google Cloud Run containers. The agent client communicates with the server using HTTP POST for requests and receives real-time tool updates via an SSE stream.

---

## 2. Handshake & Initialization Lifecycle
Every client-server connection must follow a strict three-phase initialization lifecycle:

```
  Client (Gateway)                        Server (Cloud Run)
      │                                       │
      │ ─── 1. HTTP GET /sse ───────────────> │
      │ <── 2. SSE Connection Established ─── │ (Returns client_id token)
      │                                       │
      │ ─── 3. JSON-RPC: initialize ────────> │ (Sends protocol version, capabilities)
      │ <── 4. JSON-RPC: initialized ──────── │ (Resolves tool schema validation)
```

1.  **Transport Connection**: The client initiates an SSE connection. The server responds with a unique `client_id` endpoint.
2.  **Handshake**: The client sends a JSON-RPC request calling `initialize`. This packet contains client capabilities and protocol versions.
3.  **Schema Exchange**: The server returns its capability matrix, tool list, and JSON schemas for all endpoints.

---

## 3. Error Handling and Recovery Rules
The MCP Client (FastAPI Gateway) must handle connection failures using the following HTTP / JSON-RPC rules:

*   **Initialization Timeout**: If the server fails to reply to the `initialize` handshake within **5000ms**, the client terminates the socket, reports `mcp_connection_timeout`, and suspends search requests.
*   **Tool Call Timeout**: Individual tool calls are capped at **10000ms** (except 15000ms for crawler scrapers). If an analysis scraping query hangs, the client returns JSON-RPC error code `-32603` (Internal Error) and halts the specific lead crawl thread.
*   **Schema Validation Mismatch**: If a tool call response does not match the contracts defined in [contracts/](file:///Users/ptech/Desktop/growthscout-ai/mcp/contracts/), the client ignores the data, logs a schema violation trace, and sets the lead's audit state to `validation_failed`.

---

## 4. Tool Evaluation Specifications
All MCP tools must pass evaluation checks defined in `eval/eval_config.yaml` before deployment to main staging.

### 4.1 local_business_search Evaluation
*   **Performance Metrics**:
    *   `retrieval_success_rate` (>= 95%): Valid queries (e.g. niche + city) must return >= 3 results.
    *   `latency` (average < 1500ms): Place search + details API fetches.
*   **Dataset Conformance**:
    *   Must run tests using queries in `eval/datasets/discovery_dataset.json`.
    *   Assert that tool returns valid HTTP status 200 responses.

### 4.2 web_page_fetcher / tech_footprint_scanner / seo_auditor Evaluation
*   **Performance Metrics**:
    *   `robots_compliance_accuracy` (100%): Correctly parses and blocks crawled domains where robots.txt forbids it.
    *   `scrape_success_rate` (>= 90%): Extracts raw HTML content for valid http/https endpoints.
    *   `footprint_accuracy` (>= 95%): Matches identified CMS platforms (WordPress, Shopify, etc.) against ground truth metadata in `eval/datasets/analysis_dataset.json`.
*   **Latency Bounds**:
    *   Capped at 15 seconds per crawl to prevent pipeline starvation.

---

## 5. Tool Security Validation Specifications
The MCP server gateway validates every JSON-RPC argument against the security policies before execution.

### 5.1 input Sanitization Validation
*   **Command Filter**: Rejects parameters matching: `;`, `&&`, `|`, `` ` ``, `$()`.
*   **SQL Injection Guard**: Drops query arguments containing `UNION SELECT` or `OR 1=1`.
*   **Character Limits**: Queries capped at 256 characters. URLs capped at 2048 characters.

### 5.2 SSRF Protection Gate
The `web_page_fetcher` tool must filter IPs before request dispatching:
*   **Address Check**: Resolve the target domain IP address.
*   **Blacklist Ranges**: Abort request if destination falls within loopback ranges (`127.0.0.0/8`, `::1`), private networks (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), or link-local endpoints (`169.254.169.254`).

### 5.3 Resource Exhaustion Limits
*   **Payload Bounds**: Read buffer capped at 2MB per HTTP response.
*   **Concurrency Caps**: Queue manager restricts simultaneous scrapes to 5 domains max.

