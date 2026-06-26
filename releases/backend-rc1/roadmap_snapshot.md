# GrowthScout AI — Backend RC1 Roadmap Snapshot

Following the stabilization and certification of the Backend Release Candidate 1 (RC1), the project moves forward into frontend integration and production deployments.

---

## Phase 6: FastAPI Gateway & Next.js Interface
*   **API Gateway**: Wrap the orchestrator state machine in a clean, production-grade FastAPI gateway. Expose routes for:
    *   `/workflows/start` (initiating workflow sessions).
    *   `/workflows/resume` (restarting paused tasks).
    *   `/workflows/hitl` (submitting human approvals or reviews).
*   **Web Portal**: Construct a responsive Next.js user interface representing:
    *   *Lead Discovery Dashboard*: Location/niche filters and maps list views.
    *   *Digital Footprint Viewer*: Tech stack audits and SEO matrix dashboards.
    *   *Consultative Campaign Builder*: Cold email drafts and growth report builders.
    *   *Human-in-the-Loop Gate*: Interactive revision review and comment panels.

## Phase 7: Distributed Execution & OpenTelemetry
*   **Task Queue Orchestration**: Integrate Celery or GCP Cloud Tasks to manage concurrent web presence crawls across thousands of local businesses.
*   **Observability Pipeline**: Wire OpenTelemetry exporters to route logs, spans, and metrics from `WorkflowMetricsCollector` and `AuditTrailWriter` to Google Cloud Monitoring / BigQuery.

## Phase 8: Vertex AI Agent Runtime Deployment
*   **Production Packaging**: Containerize FastMCP servers and the orchestrator engine into Docker images.
*   **Cloud Run / GKE Deployments**: Deploy services on Google Cloud Run and GKE, securing credential keys inside Google Cloud Secret Manager.
