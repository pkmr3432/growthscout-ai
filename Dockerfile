# ───────────────────────────────────────────────────────
# GrowthScout AI — Production Multi-Stage Dockerfile
# ───────────────────────────────────────────────────────
# Build:  docker build -t growthscout-ai:latest .
# Run:    docker run -p 8000:8000 --env-file .env growthscout-ai:latest
# ───────────────────────────────────────────────────────

# ── Stage 1: Builder ──────────────────────────────────
FROM python:3.14-slim AS builder

# Build arguments for version metadata
ARG BUILD_VERSION=0.0.0-dev
ARG BUILD_COMMIT=unknown
ARG BUILD_TIMESTAMP=unknown

WORKDIR /build

# Install system build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency specification first for cache-efficient builds
COPY requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Copy application source
COPY . .

# ── Stage 2: Runtime ─────────────────────────────────
FROM python:3.14-slim AS runtime

# Build arguments carried from builder
ARG BUILD_VERSION=0.0.0-dev
ARG BUILD_COMMIT=unknown
ARG BUILD_TIMESTAMP=unknown

# Set build metadata as environment variables
ENV GROWTHSCOUT_BUILD_VERSION=${BUILD_VERSION} \
    GROWTHSCOUT_BUILD_COMMIT=${BUILD_COMMIT} \
    GROWTHSCOUT_BUILD_TIMESTAMP=${BUILD_TIMESTAMP}

# Application configuration defaults
ENV APP__ENV=production \
    APP__DEBUG=false \
    APP__LOG_LEVEL=INFO \
    APP__LOG_FORMAT=json \
    API__HOST=0.0.0.0 \
    API__PORT=8000 \
    SECURITY__API_KEY_REQUIRED=true \
    STORAGE__CHECKPOINT_DIR=/data/checkpoints \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd --gid 1001 growthscout && \
    useradd --uid 1001 --gid growthscout --shell /bin/false --create-home growthscout

# Create required directories
RUN mkdir -p /app /data/checkpoints /data/logs && \
    chown -R growthscout:growthscout /app /data

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source (excluding build artifacts)
COPY --chown=growthscout:growthscout agents/ ./agents/
COPY --chown=growthscout:growthscout service/ ./service/
COPY --chown=growthscout:growthscout mcp/ ./mcp/
COPY --chown=growthscout:growthscout memory/ ./memory/
COPY --chown=growthscout:growthscout workflows/ ./workflows/
COPY --chown=growthscout:growthscout skills/ ./skills/
COPY --chown=growthscout:growthscout servers/ ./servers/
COPY --chown=growthscout:growthscout utils/ ./utils/
COPY --chown=growthscout:growthscout specs/ ./specs/

# Switch to non-root user
USER growthscout

# Expose service port
EXPOSE 8000

# Healthcheck (polls liveness endpoint every 30s)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Entrypoint: Uvicorn with single worker (scale horizontally via orchestrator)
CMD ["python", "-m", "uvicorn", "service.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "warning", \
     "--access-log", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
