# GrowthScout AI — Deployment Guide

## Overview

This guide covers deploying the GrowthScout AI service from local development through staging to production environments.

---

## Prerequisites

| Requirement | Version |
|:---|:---|
| Python | ≥ 3.11 |
| Docker | ≥ 24.0 |
| Docker Compose | ≥ 2.20 |

---

## Environment Profiles

### Development (default)

```bash
APP__ENV=development
APP__DEBUG=true
APP__LOG_LEVEL=DEBUG
APP__LOG_FORMAT=text
SECURITY__API_KEY_REQUIRED=true
SECURITY__API_KEYS='["gs_dev_key_12345"]'
STORAGE__CHECKPOINT_DIR=artifacts/checkpoints
```

### Staging

```bash
APP__ENV=staging
APP__DEBUG=false
APP__LOG_LEVEL=INFO
APP__LOG_FORMAT=json
SECURITY__API_KEY_REQUIRED=true
SECURITY__API_KEYS='["your_staging_key"]'
STORAGE__CHECKPOINT_DIR=/data/checkpoints
GEMINI_API_KEY=your_gemini_api_key
```

### Production

```bash
APP__ENV=production
APP__DEBUG=false
APP__LOG_LEVEL=WARNING
APP__LOG_FORMAT=json
SECURITY__API_KEY_REQUIRED=true
SECURITY__API_KEYS='["your_production_key_1","your_production_key_2"]'
SECURITY__ALLOWED_ORIGINS='["https://yourdomain.com"]'
SECURITY__TRUSTED_HOSTS='["yourdomain.com","api.yourdomain.com"]'
SECURITY__ENABLE_SECURITY_HEADERS=true
STORAGE__CHECKPOINT_DIR=/data/checkpoints
API__MAX_REQUEST_SIZE_BYTES=10485760
GEMINI_API_KEY=your_gemini_api_key
```

> [!IMPORTANT]
> In production, the following are required:
> - `APP__DEBUG=false`
> - `SECURITY__API_KEY_REQUIRED=true`
> - Default development API key `gs_dev_key_12345` must be removed
> - CORS wildcard `*` must be replaced with specific origins

---

## Local Development

### Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
GROWTHSCOUT_MOCK_EVAL=true python -m uvicorn service.main:app --reload --host 0.0.0.0 --port 8000
```

### With Docker

```bash
# Build the image
docker build -t growthscout-ai:dev .

# Run locally
docker run -p 8000:8000 \
  -e APP__ENV=development \
  -e APP__DEBUG=true \
  -e GROWTHSCOUT_MOCK_EVAL=true \
  -e SECURITY__API_KEYS='["gs_dev_key_12345"]' \
  -v $(pwd)/artifacts:/data/checkpoints \
  growthscout-ai:dev
```

### Verify Deployment

```bash
# Liveness
curl http://localhost:8000/health

# Readiness
curl http://localhost:8000/ready

# Startup check
curl http://localhost:8000/startup-check

# Metrics
curl http://localhost:8000/metrics
```

---

## Docker Build

### Standard Build

```bash
docker build \
  --build-arg BUILD_VERSION=1.0.0 \
  --build-arg BUILD_COMMIT=$(git rev-parse --short HEAD) \
  --build-arg BUILD_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
  -t growthscout-ai:1.0.0 .
```

### Build Arguments

| Argument | Description | Default |
|:---|:---|:---|
| `BUILD_VERSION` | Semantic version tag | `0.0.0-dev` |
| `BUILD_COMMIT` | Git commit hash | `unknown` |
| `BUILD_TIMESTAMP` | Build ISO timestamp | `unknown` |

---

## Environment Variables Reference

### Application

| Variable | Description | Default | Required |
|:---|:---|:---|:---:|
| `APP__ENV` | Environment: development, staging, production | development | ✅ |
| `APP__DEBUG` | Enable debug mode | true | ✅ |
| `APP__LOG_LEVEL` | Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL | INFO | |
| `APP__LOG_FORMAT` | Log format: json, text | json | |
| `APP__NAME` | Application name | growthscout-ai | |

### API

| Variable | Description | Default |
|:---|:---|:---|
| `API__HOST` | Bind address | 0.0.0.0 |
| `API__PORT` | Bind port | 8000 |
| `API__PREFIX` | API version prefix | /api/v1 |
| `API__MAX_REQUEST_SIZE_BYTES` | Max request body size | 10485760 |

### Security

| Variable | Description | Default |
|:---|:---|:---|
| `SECURITY__API_KEY_REQUIRED` | Enforce API key auth | true |
| `SECURITY__API_KEYS` | JSON list of valid API keys | ["gs_dev_key_12345"] |
| `SECURITY__ALLOWED_ORIGINS` | CORS allowed origins | ["*"] |
| `SECURITY__ALLOWED_HOSTS` | CORS allowed hosts | ["*"] |
| `SECURITY__TRUSTED_HOSTS` | Trusted host validation | null (disabled) |
| `SECURITY__ENABLE_SECURITY_HEADERS` | Inject security headers | true |

### Storage

| Variable | Description | Default |
|:---|:---|:---|
| `STORAGE__CHECKPOINT_DIR` | Session checkpoint directory | artifacts/checkpoints |

### External

| Variable | Description | Required |
|:---|:---|:---:|
| `GEMINI_API_KEY` | Google Gemini API key | For live execution |
| `GROWTHSCOUT_MOCK_EVAL` | Enable mock execution mode | For development |

### Build Metadata

| Variable | Description | Set By |
|:---|:---|:---|
| `GROWTHSCOUT_BUILD_VERSION` | Release version | Docker build |
| `GROWTHSCOUT_BUILD_COMMIT` | Git commit hash | Docker build |
| `GROWTHSCOUT_BUILD_TIMESTAMP` | Build timestamp | Docker build |

---

## Health Probes

| Endpoint | Purpose | Healthy Status |
|:---|:---|:---|
| `GET /health` | Liveness probe | 200 |
| `GET /ready` | Readiness probe | 200 (READY/DEGRADED) |
| `GET /startup-check` | Startup probe | 200 |
| `GET /metrics` | Prometheus metrics | 200 |

### Probe Configuration (Docker/Kubernetes)

```yaml
# Docker HEALTHCHECK (built into Dockerfile)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3

# Kubernetes (future)
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10

startupProbe:
  httpGet:
    path: /startup-check
    port: 8000
  failureThreshold: 30
  periodSeconds: 2
```

---

## Upgrade Procedure

1. **Build new image** with updated version tag
2. **Run startup-check** on new container before routing traffic
3. **Drain connections** on old container (graceful shutdown)
4. **Switch traffic** to new container
5. **Verify** via `/health`, `/ready`, `/metrics`
6. **Remove** old container

---

## Rollback Procedure

1. **Stop** current container
2. **Start** previous version container
3. **Verify** health probes pass
4. **Route traffic** to rolled-back container
5. **Investigate** failure in previous version logs
