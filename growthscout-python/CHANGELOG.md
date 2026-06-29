# Changelog — GrowthScout Python SDK

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-rc1] — 2026-06-27

### Added
- Official baseline client package layout under `growthscout/`.
- Core asynchronous HTTP client wrapper supporting standard endpoints (`create`, `get`, `run`, `submit_feedback`, `cancel`, `list_sessions`).
- Telemetry context header propagation (`X-Request-ID`, `X-Correlation-ID`).
- Custom exceptions hierarchy mapping error response statuses.
- Exponential backoff and jitter retry middleware retrying transient connections (429, 502, 503, 504).
- Server-Sent Events (SSE) stream listener supporting `Last-Event-ID` auto-reconnection.
- Automated client models alignment checks verifying synchronization with frozen OpenAPI specification.
- Local validation tests covering core functions.
