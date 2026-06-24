# Security Policy: GrowthScout AI

This policy establishes the security mandates, access regulations, and compliance standards for the GrowthScout AI monorepo.

---

## 1. Credentials and Secret Security
*   **Zero Hardcoding Policy**: Master API keys and access tokens must never be written in configuration files, comments, or repository commits.
*   **Environment Binding**: In staging and production, secrets must be loaded dynamically from **Google Cloud Secret Manager**. Local development environments must load credentials from a Git-ignored `.env` file.
*   **Rotation**: API keys for Maps and scraping proxies must be rotated every 90 days.

---

## 2. Infrastructure Access Controls
*   **Service Account Identity**: The FastAPI gateway and the Vertex AI reasoning engine must execute under distinct Google Service Accounts (IAM).
*   **Principle of Least Privilege**:
    *   `gs-gateway-sa`: Granted access only to the Cloud Run instances, Secret Manager accessor for API keys, and write privileges to the Firestore session collection.
    *   `gs-agent-sa`: Granted access to call Gemini models, trace session histories, and read Firestore session records. It is blocked from direct Secret Manager access.

---

## 3. Web Scraping Compliance and Sandboxing
*   **Robots.txt Adherence**: Crawler MCP tools must download and verify `robots.txt` allow lists before performing a scrap.
*   **Network Isolation**: The scraping proxies must execute inside an isolated virtual network segment, separated from the core backend databases, preventing Server-Side Request Forgery (SSRF) targeting internal systems.
