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
*   **Tool Call Timeout**: Individual tool calls are capped at **10000ms**. If an analysis scraping query hangs, the client returns JSON-RPC error code `-32603` (Internal Error) and halts the specific lead crawl thread.
*   **Schema Validation Mismatch**: If a tool call response does not match the contracts defined in [contracts/](file:///Users/ptech/Desktop/growthscout-ai/mcp/contracts/), the client ignores the data, logs a schema violation trace, and sets the lead's audit state to `validation_failed`.
