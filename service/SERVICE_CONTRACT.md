# GrowthScout AI — Service Contract Specification

This document defines the authoritative API contract, authentication rules, error models, streaming structures, rate limiting policies, and observability endpoints for the GrowthScout AI service layer.

---

## 1. API Versioning & Routing Guarantees

*   **Path-based Versioning**: All production REST endpoints must reside under the path prefix `/api/v1/` (e.g., `/api/v1/sessions`).
*   **Backward Compatibility Policy**:
    - Minor and patch level updates to API schemas must preserve backward compatibility.
    - Adding new optional fields to request bodies or new fields to response bodies is permitted without incrementing the major version.
    - Breaking modifications (removing fields, changing validation logic, changing types) require a new version path (`/api/v2/`).
*   **Lifecycle Verification**: Health checks `/health`, readiness probes `/ready`, and startup checks `/startup-check` are unversioned and exposed at the root level.

---

## 2. Authentication & Authorization Contract

All versioned API endpoints require authentication using the `Authenticator` interface.
*   **Method**: `X-API-Key` HTTP Header.
*   **Unauthorized Behavior**: Requests without a valid key yield an HTTP `401 Unauthorized` response with a structured JSON error payload.
*   **Forbidden Behavior**: Requests with a valid key but insufficient scope yield an HTTP `403 Forbidden` response.

---

## 3. Structured Error Model

All API errors must return a standardized JSON structure with the `application/json` content type.

### Schema Definition
```json
{
  "error": {
    "code": "string",
    "message": "string",
    "request_id": "string",
    "correlation_id": "string",
    "timestamp": "ISO-8601 string",
    "retryable": "boolean",
    "details": "object | null"
  }
}
```

### Error Code Registry
- `AUTHENTICATION_FAILED`: Invalid API key or missing header.
- `AUTHORIZATION_FAILED`: Insufficient scope for request.
- `SESSION_LOCKED`: The requested session is already running a background task.
- `SESSION_NOT_FOUND`: No session found matching the supplied `session_id`.
- `INVALID_TRANSITION`: The state transition request does not comply with workflow rules.
- `RATE_LIMIT_EXCEEDED`: Client has exceeded the configured request rate limit.
- `SCHEDULER_FAILED`: Background task scheduling failed.
- `INTERNAL_SERVER_ERROR`: An unhandled exception occurred in the service layer.

---

## 4. Streaming & Event SSE Contract

The `/api/v1/sessions/{session_id}/stream` endpoint implements Server-Sent Events (SSE) using the `text/event-stream` media type.

### Event Envelope Schema

Every SSE event conforms to the canonical `EventEnvelope` structure:
```json
{
  "event_id": 1,
  "event_type": "execution_started",
  "session_id": "sess_abc123",
  "timestamp": "2026-06-27T00:00:00Z",
  "data": {},
  "correlation_id": "corr_xyz"
}
```

### SSE Wire Format
```
id: {event_id}
event: {event_type}
data: {json_payload}
```

### Event Type Registry
| Event Type | Description |
|:---|:---|
| `stream_connected` | Emitted immediately when the SSE connection is established. |
| `execution_started` | Emitted when the task engine launches a workflow run. |
| `state_changed` | Emitted on session state machine transitions. |
| `step_completed` | Emitted when an agent completes a workflow node transition. |
| `gate_reached` | Emitted when HITL validation halts the run. |
| `execution_completed` | Emitted when the orchestrator hits a terminal state. |
| `execution_failed` | Emitted when the execution encounters a failure. |
| `execution_cancelled` | Emitted when the execution is cancelled. |
| `heartbeat` | Emitted every 15 seconds to keep the connection alive. |
| `stream_ended` | Sentinel event signaling the stream is closing. |

### Response Headers
| Header | Value |
|:---|:---|
| `Content-Type` | `text/event-stream` |
| `Cache-Control` | `no-cache, no-store, must-revalidate` |
| `X-Accel-Buffering` | `no` |
| `Connection` | `keep-alive` |

### Replay Support (Last-Event-ID)

The streaming endpoint supports client reconnection using the standard `Last-Event-ID` HTTP header.

*   **Mechanism**: On reconnect, the client sends `Last-Event-ID: {event_id}` in the request headers.
*   **Behavior**: The server replays all events with `event_id > Last-Event-ID` from its bounded in-memory replay buffer before resuming live streaming.
*   **Buffer Size**: The default replay buffer retains the last 256 events per session.
*   **Buffer Scope**: Replay buffers are per-session and are cleaned up when a session stream closes.

### Stream Lifecycle

1.  Client opens `GET /api/v1/sessions/{session_id}/stream` with valid `X-API-Key`.
2.  Server validates session exists (returns 404 if not found).
3.  Server emits `stream_connected` event (event_id=0).
4.  If `Last-Event-ID` is provided, missed events are replayed from the buffer.
5.  Live events are streamed as the workflow executes.
6.  Heartbeat events are emitted every 15 seconds during inactivity.
7.  When execution reaches a terminal state or is cancelled, `stream_ended` is emitted.
8.  Client may safely close the connection at any point.

---

## 5. Rate Limiting Contract

A token bucket rate limiter protects all versioned API endpoints.

### Configuration
| Parameter | Default | Description |
|:---|:---|:---|
| `requests_per_second` | 10.0 | Sustained request rate per client. |
| `burst_capacity` | 20 | Maximum burst size before throttling. |

### Client Identification
Clients are identified by their `X-API-Key` header value. If no API key is present, the client IP address is used as a fallback.

### Excluded Paths
The following paths are excluded from rate limiting:
- `/health`, `/ready`, `/startup-check`
- `/metrics`
- `/openapi.json`, `/docs`, `/redoc`

### Rate Limit Response (HTTP 429)
When the rate limit is exceeded, the server returns HTTP `429 Too Many Requests` with:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Retry after X seconds.",
    "retryable": true,
    "details": {
      "retry_after_seconds": 0.5,
      "limit": 10.0,
      "burst_capacity": 20
    }
  }
}
```

### Rate Limit Response Headers
| Header | Description |
|:---|:---|
| `X-RateLimit-Limit` | Maximum burst capacity. |
| `X-RateLimit-Remaining` | Tokens remaining in the bucket. |
| `X-RateLimit-Reset` | Unix timestamp when the bucket will be fully refilled. |
| `Retry-After` | Seconds to wait before retrying (on 429 responses). |

---

## 6. Observability & Metrics Contract

### Prometheus Metrics Endpoint

The `/metrics` endpoint exposes application metrics in Prometheus text exposition format.

**Content-Type**: `text/plain; version=0.0.4; charset=utf-8`

### Metrics Registry
| Metric | Type | Description |
|:---|:---|:---|
| `growthscout_uptime_seconds` | gauge | Time since application start. |
| `growthscout_requests_total` | counter | Total HTTP requests handled. |
| `growthscout_errors_total` | counter | Total error responses returned. |
| `growthscout_active_tasks` | gauge | Currently running background workflow tasks. |
| `growthscout_tracked_tasks_total` | gauge | Total tasks tracked by scheduler. |
| `growthscout_active_locks` | gauge | Currently held session locks. |
| `growthscout_sse_subscribers` | gauge | Active SSE streaming subscribers. |
| `growthscout_events_published_total` | counter | Total events published to SSE subscribers. |

### Telemetry Headers
Every HTTP response includes tracing headers injected by the telemetry middleware:
| Header | Description |
|:---|:---|
| `X-Request-ID` | Unique request trace identifier. |
| `X-Correlation-ID` | Correlation ID tying related requests together. |
| `X-Process-Time` | Server-side processing duration. |

---

## 7. Security Headers Contract

All HTTP responses include the following security headers:

| Header | Value | Purpose |
|:---|:---|:---|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restrict browser features |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | HSTS (production only) |

---

## 8. Request Size Limits

*   **Maximum Request Body**: Configurable via `API__MAX_REQUEST_SIZE_BYTES` (default: 10MB / 10,485,760 bytes).
*   **Rejection**: Requests exceeding the limit receive HTTP `413 Payload Too Large` with error code `PAYLOAD_TOO_LARGE`.

---

## 9. Configuration Validation

### Production Requirements
The service validates configuration on startup. In production (`APP__ENV=production`):

| Requirement | Validation |
|:---|:---|
| Debug mode | `APP__DEBUG` must be `false` |
| API key auth | `SECURITY__API_KEY_REQUIRED` must be `true` |
| Default dev key | `gs_dev_key_12345` must be removed from `SECURITY__API_KEYS` |
| CORS origins | Wildcard `*` not allowed in `SECURITY__ALLOWED_ORIGINS` |

Failure to meet production requirements causes immediate service shutdown (exit code 1).

