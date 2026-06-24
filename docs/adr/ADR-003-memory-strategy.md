# ADR-003: Memory and Knowledge Strategy

## Status
Approved

## Context
Our agents need access to past conversational turns, historical business audits, and consultant preferences. Dumping all historical data into the LLM prompt on every query will blow past the token budget and cause the model to ignore critical instructions.

We need a tiered memory architecture that balances short-term session recall with long-term business profile storage.

## Decisions
1.  **Tier 1: Ephemeral Session Memory**: Handled by Vertex AI Agent Runtime session stores. Extracted session state logs expire after 90 days.
2.  **Tier 2: Persistent SMB Knowledge Graph**: Analyzed business profiles are serialized and stored permanently in Cloud Firestore.
3.  **Tier 3: Long-Term Preference Recall**: Managed through the Vertex AI Memory Bank index. High-level facts (e.g., "Consultant prefers casual emails") are embedded and queried using vector search.
4.  **Vector Search Indexing**: We set a similarity threshold of `0.82` for lead verification checks.

## Consequences
*   **Positives**: Kept token footprint small. Avoids redundant scraping by querying Firestore profiles before performing fresh website crawls.
*   **Negatives**: Requires database reads/writes at multiple orchestration steps.
*   **Mitigations**: Implement an indexing cache layer on the FastAPI gateway to retrieve profiles instantly.
