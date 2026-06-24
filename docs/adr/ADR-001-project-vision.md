# ADR-001: Project Vision and Stack Selection

## Status
Approved

## Context
We are designing a production-grade AI platform called **GrowthScout AI** to help agency consultants discover local businesses, audit their technical footprints, and compile Growth Intelligence Reports. We need to select a core stack that:
1.  Provides robust asynchronous performance for crawler tools.
2.  Supports dynamic frontend components with high design aesthetic standards.
3.  Leverages Google's Agent Development Kit (ADK) for managed, traceable multi-agent environments.

## Decisions
1.  **Backend Framework**: FastAPI (Python 3.11+). It supports native async operations, automatically generates OpenAPI documentation, and integrates directly with Google Vertex AI SDKs.
2.  **Frontend Framework**: Next.js 14+ (React) for structured component management, Server-Side Rendering (SSR), and seamless production routing.
3.  **Agent Engine**: Google ADK SDK. We reject custom langchain/langgraph setups to maintain compliance with Vertex AI Agent Runtime session services and native Cloud Trace observability.
4.  **Integration Layer**: Model Context Protocol (MCP) for tool bindings, keeping the crawler logic isolated from the LLM execution loops.

## Consequences
*   **Positives**: Clear component separation. Frontend developers can build UI grids in Next.js independently, while agent developers write modular skills in Python.
*   **Negatives**: Introduces multi-tier networking and requires maintaining local MCP hosts.
*   **Mitigations**: Codify strict schemas (`api_spec.yaml` and MCP tool contracts) before development to prevent API mismatch.
