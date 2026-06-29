# service/api/routers/health.py
"""
Liveness, Readiness, and Startup checkpoints routing.

Supports READY, DEGRADED, and NOT_READY classifications with version,
build information, uptime, and deployment mode metadata.
"""

import sys
import os
import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, status, HTTPException
from service.infrastructure.config import ServiceSettings, get_build_info
from service.api.dependencies import get_settings

router = APIRouter(tags=["Health & Status Checks"])

# Application start time for uptime calculation
_app_start_time = time.time()


class LivenessResponse(BaseModel):
    status: str = Field("healthy", description="Liveness status of the service (always 'healthy')")
    version: str = Field(..., description="Service version metadata")
    uptime_seconds: float = Field(..., description="Uptime of the service in seconds")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "healthy",
                    "version": "1.0.0-rc1",
                    "uptime_seconds": 124.52
                }
            ]
        }
    }


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Readiness status (READY or DEGRADED)")
    checks: Dict[str, str] = Field(..., description="Status breakdown of specific system checkpoints")
    reasons: Optional[List[str]] = Field(None, description="Optional reasons if state is DEGRADED")
    environment: str = Field(..., description="Active deployment environment name")
    version: str = Field(..., description="Service version metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "READY",
                    "checks": {
                        "checkpoint_storage": "ok",
                        "service_registry": "ok",
                        "event_publisher": "ok",
                        "gemini_api_key": "ok",
                        "configuration": "ok"
                    },
                    "environment": "production",
                    "version": "1.0.0-rc1"
                }
            ]
        }
    }


class StartupCheckResponse(BaseModel):
    status: str = Field("passed", description="Startup checkpoint state (always 'passed')")
    python_version: str = Field(..., description="Host python platform compatibility version")
    environment_check: str = Field("compatible", description="Platform compatibility marker")
    version: str = Field(..., description="Service version metadata")
    commit: str = Field(..., description="Build commit identifier")
    build_timestamp: str = Field(..., description="ISO build timestamp")
    environment: str = Field(..., description="Active deployment environment name")
    debug: bool = Field(..., description="Debug logging flag state")
    uptime_seconds: float = Field(..., description="Uptime of the service in seconds")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "passed",
                    "python_version": "3.14",
                    "environment_check": "compatible",
                    "version": "1.0.0-rc1",
                    "commit": "a1b2c3d4",
                    "build_timestamp": "2026-06-27T22:39:22Z",
                    "environment": "production",
                    "debug": False,
                    "uptime_seconds": 124.52
                }
            ]
        }
    }


@router.get(
    "/health",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    operation_id="livenessCheck",
    summary="Liveness Check Probe",
    description="Returns HTTP 200 with uptime and version metadata if the FastAPI application process is alive."
)
async def health_check():
    build_info = get_build_info()
    return LivenessResponse(
        status="healthy",
        version=build_info["version"],
        uptime_seconds=round(time.time() - _app_start_time, 2)
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    operation_id="readinessCheck",
    summary="Readiness Check Probe",
    description="Verifies underlying system dependencies (checkpoint storage, service registry initialization, and configuration) and returns READY, DEGRADED, or NOT_READY.",
    responses={
        503: {"description": "Service Unavailable - Critical dependencies are NOT_READY"}
    }
)
async def readiness_check(settings: ServiceSettings = Depends(get_settings)):
    checkpoint_dir = settings.storage.checkpoint_dir
    checks = {}
    degraded_reasons = []

    # 1. Verify Checkpoints Storage (Critical Dependency)
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
        return ReadinessResponse(
            status="DEGRADED",
            checks=checks,
            reasons=degraded_reasons,
            environment=settings.app.env,
            version=build_info["version"]
        )

    return ReadinessResponse(
        status="READY",
        checks=checks,
        environment=settings.app.env,
        version=build_info["version"]
    )


@router.get(
    "/startup-check",
    response_model=StartupCheckResponse,
    status_code=status.HTTP_200_OK,
    operation_id="startupCheck",
    summary="Startup Compatibility Check",
    description="Asserts host Python platform compatibility, deployment configuration profiles, and version tags on initial container launch."
)
async def startup_check(settings: ServiceSettings = Depends(get_settings)):
    major, minor = sys.version_info.major, sys.version_info.minor
    if (major, minor) < (3, 11):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"status": "failed", "reason": f"Incompatible Python version {major}.{minor}"}
        )

    build_info = get_build_info()

    return StartupCheckResponse(
        status="passed",
        python_version=f"{major}.{minor}",
        environment_check="compatible",
        version=build_info["version"],
        commit=build_info["commit"],
        build_timestamp=build_info["build_timestamp"],
        environment=settings.app.env,
        debug=settings.app.debug,
        uptime_seconds=round(time.time() - _app_start_time, 2)
    )
