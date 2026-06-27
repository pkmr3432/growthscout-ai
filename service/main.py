# service/main.py
"""
FastAPI Gateway Application Entrypoint & Bootstrap.

Implements deterministic startup and shutdown lifecycle ordering,
structured logging, security middleware, and rate limiting.
"""

import time
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from service.infrastructure.config import settings, get_build_info
from service.infrastructure.registry import registry
from service.infrastructure.logging import configure_logging, RequestContextFilter
from service.api.routers import health, sessions, metrics
from service.middleware.rate_limit import RateLimitMiddleware
from service.middleware.security import SecurityHeadersMiddleware, RequestSizeLimitMiddleware
from service.api.routers.metrics import increment_request_counter, increment_error_counter

logger = logging.getLogger("growthscout.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Deterministic service startup and shutdown lifecycle.

    Startup Order:
        1. Configure logging
        2. Validate configuration
        3. Initialize registry (storage, publisher, scheduler)
        4. Log startup complete

    Shutdown Order:
        1. Log shutdown initiated
        2. Cancel active tasks
        3. Close publisher streams
        4. Shutdown registry
        5. Log shutdown complete
    """
    # ── STARTUP ──
    configure_logging(
        log_level=settings.app.log_level,
        log_format=settings.app.log_format,
        service_name=settings.telemetry.service_name
    )

    build_info = get_build_info()
    logger.info(
        f"GrowthScout AI Service starting — "
        f"env={settings.app.env}, "
        f"version={build_info['version']}, "
        f"debug={settings.app.debug}"
    )

    await registry.initialize()
    logger.info("Service startup complete — accepting requests")

    yield

    # ── SHUTDOWN ──
    logger.info("Service shutdown initiated — draining connections...")
    await registry.shutdown()
    logger.info("Service shutdown complete")


# ── Application Factory ──
app = FastAPI(
    title=settings.app.name,
    description="Production Service API Gateway for GrowthScout AI Orchestrator",
    version=get_build_info()["version"],
    debug=settings.app.debug,
    docs_url="/docs" if settings.app.debug or settings.is_development else None,
    redoc_url="/redoc" if settings.app.debug or settings.is_development else None,
    lifespan=lifespan
)


# ── Middleware Stack (applied in reverse order) ──

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# 2. Security headers
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=settings.is_production,
)

# 3. Request size limit
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_size_bytes=settings.api.max_request_size_bytes,
)

# 4. Rate limiter
app.add_middleware(
    RateLimitMiddleware,
    requests_per_second=10.0,
    burst_capacity=20
)


# ── Telemetry Middleware ──
@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    start_time = time.time()
    increment_request_counter()

    # Resolve telemetry parameters from request headers or generate defaults
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    correlation_id = request.headers.get("X-Correlation-ID", request_id)
    session_id = request.headers.get("X-Session-ID", "none")
    workflow_id = request.headers.get("X-Workflow-ID", "none")
    recovery_id = request.headers.get("X-Recovery-ID", "none")

    # Store request scope state for downstream dependency checks
    request.state.request_id = request_id
    request.state.correlation_id = correlation_id
    request.state.session_id = session_id
    request.state.workflow_id = workflow_id
    request.state.recovery_id = recovery_id

    # Set logging context for structured logs
    RequestContextFilter.set_context(
        request_id=request_id,
        correlation_id=correlation_id,
        session_id=session_id,
        workflow_id=workflow_id
    )

    response: Response = await call_next(request)

    # Inject tracing headers into response
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Session-ID"] = session_id
    response.headers["X-Workflow-ID"] = workflow_id
    response.headers["X-Recovery-ID"] = recovery_id

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"

    # Clear logging context
    RequestContextFilter.clear_context()

    return response


# ── Error Handlers ──

def make_error_response(
    code: str,
    message: str,
    request: Request,
    status_code: int,
    retryable: bool = False,
    details: dict = None
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
                "correlation_id": correlation_id,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "retryable": retryable,
                "details": details
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    message = "Request payload validation failed."
    if errors:
        loc = ".".join(str(p) for p in errors[0].get("loc", []))
        message = f"Validation failed: {errors[0].get('msg', 'invalid field')} at '{loc}'."
    return make_error_response(
        code="BAD_REQUEST",
        message=message,
        request=request,
        status_code=status.HTTP_400_BAD_REQUEST,
        details={"validation_errors": errors}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    code = "BAD_REQUEST"
    message = str(exc.detail)
    details = None
    retryable = False

    if isinstance(exc.detail, dict) and "error" in exc.detail:
        err = exc.detail["error"]
        code = err.get("code", "BAD_REQUEST")
        message = err.get("message", message)
        details = err.get("details", None)
        retryable = err.get("retryable", False)

    return make_error_response(
        code=code,
        message=message,
        request=request,
        status_code=exc.status_code,
        retryable=retryable,
        details=details
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    increment_error_counter()
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return make_error_response(
        code="INTERNAL_SERVER_ERROR",
        message=f"An unexpected runtime error occurred: {str(exc)}",
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        retryable=False
    )


# ── Route Registration ──

# Health check endpoints (root level, unversioned)
app.include_router(health.router)

# Metrics endpoint (root level)
app.include_router(metrics.router)

# Versioned API router
app.include_router(sessions.router, prefix=settings.api.prefix)
