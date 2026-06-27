# GrowthScout AI — Operations Runbook

## Service Architecture

```
Client → Nginx/LB → FastAPI (Uvicorn) → Orchestrator → Workers → MCP Servers
                 ↕                    ↕
           Rate Limiter          SSE Publisher
                                     ↕
                              Checkpoint Store
```

---

## Service Endpoints

| Endpoint | Method | Purpose |
|:---|:---|:---|
| `/health` | GET | Liveness probe |
| `/ready` | GET | Readiness probe (READY/DEGRADED/NOT_READY) |
| `/startup-check` | GET | Platform compatibility verification |
| `/metrics` | GET | Prometheus-compatible metrics |
| `/api/v1/sessions` | POST | Create new session |
| `/api/v1/sessions/{id}` | GET | Retrieve session state |
| `/api/v1/sessions/{id}/run` | POST | Start workflow execution |
| `/api/v1/sessions/{id}/cancel` | POST | Cancel execution |
| `/api/v1/sessions/{id}/feedback` | POST | Submit HITL feedback |
| `/api/v1/sessions/{id}/stream` | GET | SSE event stream |

---

## Monitoring

### Key Metrics

| Metric | Type | Alert Threshold |
|:---|:---|:---|
| `growthscout_uptime_seconds` | gauge | < 60s (frequent restarts) |
| `growthscout_requests_total` | counter | Normal baseline |
| `growthscout_errors_total` | counter | > 5% of requests |
| `growthscout_active_tasks` | gauge | > 10 concurrent |
| `growthscout_active_locks` | gauge | > 10 concurrent |
| `growthscout_sse_subscribers` | gauge | > 50 concurrent |

### Log Analysis

Structured JSON logs can be queried using standard tools:

```bash
# Find errors
docker logs growthscout-ai 2>&1 | jq 'select(.level == "ERROR")'

# Find slow requests
docker logs growthscout-ai 2>&1 | jq 'select(.level == "WARNING")'

# Filter by session
docker logs growthscout-ai 2>&1 | jq 'select(.session_id == "sess_abc123")'

# Filter by correlation ID
docker logs growthscout-ai 2>&1 | jq 'select(.correlation_id == "corr_xyz")'
```

---

## Troubleshooting

### Service Won't Start

| Symptom | Cause | Resolution |
|:---|:---|:---|
| Exit code 1 on startup | Configuration validation failure | Check APP__ENV, SECURITY settings |
| `/ready` returns NOT_READY | Checkpoint directory not writable | Check permissions on STORAGE__CHECKPOINT_DIR |
| `/ready` returns DEGRADED | Missing GEMINI_API_KEY | Set GEMINI_API_KEY for live execution |

### Common Issues

#### 1. HTTP 429 Too Many Requests
**Cause**: Client exceeded rate limit (10 req/s, burst 20).
**Resolution**: Implement exponential backoff. Check `Retry-After` header.

#### 2. HTTP 409 Session Locked
**Cause**: Concurrent execution attempt on same session.
**Resolution**: Wait for current execution to complete, or cancel it.

#### 3. HTTP 413 Payload Too Large
**Cause**: Request body exceeds `API__MAX_REQUEST_SIZE_BYTES`.
**Resolution**: Reduce payload size or increase limit.

#### 4. SSE Stream Disconnects
**Cause**: Network timeout, proxy buffering, or server restart.
**Resolution**: Reconnect with `Last-Event-ID` header. Ensure proxy has `X-Accel-Buffering: no`.

#### 5. Checkpoint Data Missing
**Cause**: Container restarted without persistent volume.
**Resolution**: Mount persistent volume to `STORAGE__CHECKPOINT_DIR`.

---

## Operational Procedures

### Restarting the Service

```bash
# Graceful restart (Docker)
docker restart growthscout-ai

# Force restart
docker stop growthscout-ai && docker start growthscout-ai
```

### Viewing Logs

```bash
# Real-time logs
docker logs -f growthscout-ai

# Last 100 lines
docker logs --tail 100 growthscout-ai

# Since timestamp
docker logs --since "2026-06-27T00:00:00" growthscout-ai
```

### Checking Resource Usage

```bash
docker stats growthscout-ai
```

### Emergency API Key Rotation

1. Generate new API key(s)
2. Update `SECURITY__API_KEYS` environment variable
3. Restart the service
4. Verify with: `curl -H "X-API-Key: NEW_KEY" http://localhost:8000/health`
5. Revoke old keys from clients

### Clearing Checkpoint State

```bash
# WARNING: This will lose all in-flight session state
docker exec growthscout-ai rm -rf /data/checkpoints/*
docker restart growthscout-ai
```

---

## Graceful Shutdown Sequence

When the service receives SIGTERM:

1. **Stop accepting new requests** — FastAPI stops routing
2. **Cancel active tasks** — TaskScheduler cancels all background workflows
3. **Close SSE streams** — EventPublisher sends `stream_ended` to all subscribers
4. **Flush metrics** — Final metric values are available until process exits
5. **Shutdown registry** — Resources released
6. **Exit** — Process terminates cleanly

> [!NOTE]
> Docker sends SIGTERM and waits 10 seconds before SIGKILL.
> Ensure `--stop-timeout` is set appropriately for long-running workflows.

---

## Security Checklist

- [ ] `APP__DEBUG=false` in production
- [ ] Default dev API key removed from `SECURITY__API_KEYS`
- [ ] CORS origins restricted (no wildcard `*`)
- [ ] `SECURITY__ENABLE_SECURITY_HEADERS=true`
- [ ] GEMINI_API_KEY not embedded in Docker image
- [ ] Container runs as non-root user (UID 1001)
- [ ] No `.env` files baked into image
- [ ] TLS termination handled by reverse proxy
