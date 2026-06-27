# service/api/routers/health.py
"""
Liveness, Readiness, and Startup checkpoints routing.

Supports READY, DEGRADED, and NOT_READY classifications with version,
build information, uptime, and deployment mode metadata.
"""

import sys
import os
import time
from fastapi import APIRouter, Depends, status, HTTPException
from service.infrastructure.config import ServiceSettings, get_build_info
from service.api.dependencies import get_settings

router = APIRouter(tags=["Health & Status Checks"])

# Application start time for uptime calculation
_app_start_time = time.time()


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Liveness Check: Returns 200 if the FastAPI application process is alive.
    Includes version and uptime metadata.
    """
    build_info = get_build_info()
    return {
        "status": "healthy",
        "version": build_info["version"],
        "uptime_seconds": round(time.time() - _app_start_time, 2)
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check(settings: ServiceSettings = Depends(get_settings)):
    """
    Readiness Check: Verifies dependencies and returns READY, DEGRADED, or NOT_READY.

    Checks:
    1. Checkpoint storage directory is writable (critical)
    2. Service registry is initialized
    3. Event publisher is available
    4. GEMINI_API_KEY is configured (non-critical)

    Returns:
    - READY: All checks pass
    - DEGRADED: Non-critical checks fail (e.g., missing GEMINI_API_KEY)
    - NOT_READY: Critical checks fail (returns HTTP 503)
    """
    checks = {}
    degraded_reasons = []

    # 1. Verify Checkpoints Storage (Critical Dependency)
    checkpoint_dir = settings.storage.checkpoint_dir
    try:
        os.makedirs(checkpoint_dir, exist_ok=True)
        test_file = os.path.join(checkpoint_dir, ".readiness_check")
        with open(test_file, "w") as f:
            f.write("OK")
        os.remove(test_file)
        checks["checkpoint_storage"] = "ok"
    except Exception as e:
        # NOT_READY — critical failure
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "NOT_READY",
                "checks": {"checkpoint_storage": f"failed: {str(e)}"},
                "reason": f"Storage checkpoints directory is not writable: {str(e)}"
            }
        )

    # 2. Verify Service Registry
    try:
        from service.infrastructure.registry import registry
        if registry.lock_manager and registry.task_scheduler and registry.checkpoint_store:
            checks["service_registry"] = "ok"
        else:
            checks["service_registry"] = "degraded"
            degraded_reasons.append("Service registry components not fully initialized")
    except Exception as e:
        checks["service_registry"] = f"failed: {str(e)}"
        degraded_reasons.append(f"Service registry check failed: {str(e)}")

    # 3. Verify Event Publisher
    try:
        from service.infrastructure.registry import registry
        if registry.event_publisher:
            checks["event_publisher"] = "ok"
        else:
            checks["event_publisher"] = "degraded"
            degraded_reasons.append("Event publisher not initialized")
    except Exception as e:
        checks["event_publisher"] = f"failed: {str(e)}"
        degraded_reasons.append(f"Event publisher check failed: {str(e)}")

    # 4. Verify external API key availability
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        checks["gemini_api_key"] = "missing"
        degraded_reasons.append("GEMINI_API_KEY environment variable is not configured. Live execution unavailable.")
    else:
        checks["gemini_api_key"] = "ok"

    # 5. Configuration validation
    config_errors = settings.validate_production_requirements()
    if config_errors:
        checks["configuration"] = "warnings"
        degraded_reasons.extend(config_errors)
    else:
        checks["configuration"] = "ok"

    build_info = get_build_info()

    if degraded_reasons:
        return {
            "status": "DEGRADED",
            "checks": checks,
            "reasons": degraded_reasons,
            "environment": settings.app.env,
            "version": build_info["version"]
        }

    return {
        "status": "READY",
        "checks": checks,
        "environment": settings.app.env,
        "version": build_info["version"]
    }


@router.get("/startup-check", status_code=status.HTTP_200_OK)
async def startup_check(settings: ServiceSettings = Depends(get_settings)):
    """
    Startup Check: Validates platform compatibility and configuration.

    Returns version, build information, uptime, and deployment mode.
    """
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) < (3, 11):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "failed", "reason": f"Incompatible Python version {major}.{minor}"}
        )

    build_info = get_build_info()

    return {
        "status": "passed",
        "python_version": f"{major}.{minor}",
        "environment_check": "compatible",
        "version": build_info["version"],
        "commit": build_info["commit"],
        "build_timestamp": build_info["build_timestamp"],
        "environment": settings.app.env,
        "debug": settings.app.debug,
        "uptime_seconds": round(time.time() - _app_start_time, 2)
    }
