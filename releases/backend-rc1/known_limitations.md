# GrowthScout AI — Backend RC1 Known Limitations

This document lists the known limitations, operational assumptions, and environment boundaries for the **Backend Release Candidate 1 (RC1)** release.

---

## 1. External Credentials Dependency
*   The orchestrator and worker agents rely on active `GEMINI_API_KEY` and `GOOGLE_MAPS_API_KEY` environment variables.
*   **Offline Mode:** If keys are missing, the automated regression test suite and benchmark suite gracefully run using mocks, stubs, and simulated pipelines. Preflight smoke tests verify the system infrastructure but flag key absences as configuration warnings.

## 2. FastMCP Process Execution
*   Dry-run and active preflight MCP readiness checks execute subprocess commands using `sys.executable` to align FastMCP servers with the active Python virtual environment.
*   The host system must have the virtual environment activated (`.venv`) with all dependency manifests installed, or preflight MCP process acquisition will fail.

## 3. Vertex AI Agent Runtime Mappings
*   The worker registries map configuration definitions to Gemini AI Studio model defaults (e.g. `gemini-1.5-flash-002` and `gemini-1.5-pro-002`).
*   Production systems deployed to Vertex AI Runtime must ensure these model names are mapped or configured to support target production engines (e.g., `gemini-2.5-flash` or newer).

## 4. Firestore Checkpoint Backend Timeout
*   The Firestore backend wrapper utilizes a strict, configurable `firestore_timeout_seconds` limit (default: 15s). Under extremely slow networks, Firestore connection timeouts may trigger circuit breaker openings. Ensure the timeout is scaled appropriately for the deployment region.
