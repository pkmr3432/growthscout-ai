# Operational Playbook: GrowthScout AI

This playbook defines the operational procedures for deploying, scaling, monitoring, and troubleshooting the GrowthScout AI platform.

---

## 1. Secrets Management Policy
*   **Storage**: Under no circumstances may API keys (Google Maps API, Scraping Proxy credentials, LLM keys) be stored in `.env` files or code repositories in production.
*   **Retrieval**: Deployments must read secrets dynamically from **Google Cloud Secret Manager**.
*   **IAM Policies**: The service accounts running the FastAPI Cloud Run instances and the Vertex AI Reasoning Engines must have the role `roles/secretmanager.secretAccessor` granted *only* for their required secrets.

---

## 2. Infrastructure Deployment Flow
To deploy updates to the active environment:
1.  **Run Evaluation Suite**: Verify that the code passes all gates.
2.  **Containerize Services**: Build Docker images for the FastAPI gateway and MCP servers, and push them to Google Artifact Registry.
3.  **Deploy Backend & MCP**:
    ```bash
    # Deploy Gateway API
    gcloud run deploy gs-gateway \
      --image us-central1-docker.pkg.dev/gs-prod/ar/gateway:latest \
      --service-account=gs-gateway-sa@gs-prod.iam.gserviceaccount.com \
      --region=us-central1
    ```
4.  **Register ADK Agents**:
    ```bash
    # Deploy agent specifications to Vertex AI Reasoning Engines
    agents-cli deploy
    ```

---

## 3. Observability and Monitoring

### Trace logs
All agent executions are logged to **Google Cloud Trace** via the ADK session service. When troubleshooting a failed recommendation:
1.  Open the Google Cloud Console -> Trace List.
2.  Filter by `session_id`.
3.  Examine the spans representing the `Business Discovery Agent` maps query or the `Website Analysis Agent` fetch trace.

### BigQuery Agent Analytics
Prompt and response pairs are exported asynchronously to a BigQuery dataset (`gs_agent_analytics.traces`) to audit output quality, input injection occurrences, and latency trends.

---

## 4. Rate Limiting and Backoff Policies
*   **Local Maps API**: Bound to 10 queries per minute per user session to avoid maps quota limits.
*   **Scraper MCP Server**: Must enforce a 2-second delay between requests to the same domain. If target returns HTTP 429, implement exponential backoff:
    *   *Retry 1*: Wait 5s
    *   *Retry 2*: Wait 15s
    *   *Retry 3*: Mark URL as "Crawling Blocked (Rate Limited)" and abort.
