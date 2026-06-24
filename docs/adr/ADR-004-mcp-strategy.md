# ADR-004: Model Context Protocol (MCP) Integration

## Status
Approved

## Context
Our agents require access to Google Maps queries, raw website content scraping, and SEO analysis engines. Hardcoding API clients, rate limiters, proxy networks, and HTML parsers directly inside ADK Agent logic creates code bloat and complicates prompt design.

We need a clean, standard protocol to bridge our agent decision loops with local and third-party tools.

## Decisions
1.  **Standardization on MCP**: All external API integrations must run via Model Context Protocol (MCP) JSON-RPC channels.
2.  **Server Isolation**: MCP Servers (Local Search and Web Analyzer) are deployed as isolated Docker containers on Cloud Run.
3.  **Client Hosting**: The FastAPI Gateway acts as the MCP client host, establishing secure SSE (Server-Sent Events) bindings to the active servers.
4.  **No Server-Side Agent Credentials**: The MCP servers must not store master Google Maps or Scraping keys. API credentials must be passed dynamically from the client (supplied via Secret Manager).

## Consequences
*   **Positives**: Excellent isolation. The Website Analysis Agent only sees the schema contracts (e.g., `local_search_tool_schema.json`), meaning we can update scraper libraries (like BeautifulSoup/Playwright) without changing the agent's prompts.
*   **Negatives**: Adds JSON-RPC overhead to tool calls.
*   **Mitigations**: Implement connection pooling and local caching of scraper records.
