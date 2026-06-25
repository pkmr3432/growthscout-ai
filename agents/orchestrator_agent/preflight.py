# agents/orchestrator_agent/preflight.py
import asyncio
from enum import Enum
import os
import time
from typing import List, Literal, Optional
from pydantic import BaseModel
from .runtime_config import RuntimeConfig
from .error_codes import RuntimeErrorCode, GrowthScoutRuntimeError

class HealthCategory(str, Enum):
    CONFIGURATION = "CONFIGURATION"
    AUTHENTICATION = "AUTHENTICATION"
    CONNECTIVITY = "CONNECTIVITY"
    DEPENDENCIES = "DEPENDENCIES"
    RUNTIME = "RUNTIME"
    EXTERNAL_SERVICES = "EXTERNAL_SERVICES"

class HealthCheckResult(BaseModel):
    category: HealthCategory
    component: str
    status: Literal["UP", "DOWN"]
    latency_ms: float
    message: str
    error_code: Optional[RuntimeErrorCode] = None

class PreflightValidator:
    def __init__(self, config: RuntimeConfig) -> None:
        self.config = config

    async def run_checks(self) -> List[HealthCheckResult]:
        results = []

        # 1. Check version compatibility
        start_time = time.perf_counter()
        try:
            cfg_parts = [int(x) for x in self.config.config_version.split(".")]
            min_parts = [int(x) for x in self.config.minimum_supported_version.split(".")]
            if cfg_parts < min_parts:
                raise GrowthScoutRuntimeError(
                    error_code=RuntimeErrorCode.CONFIGURATION_ERROR,
                    message=f"Incompatible config version: config_version {self.config.config_version} "
                            f"is less than minimum_supported_version {self.config.minimum_supported_version}.",
                    service=None,
                    retryable=False,
                )
            latency = (time.perf_counter() - start_time) * 1000.0
            results.append(HealthCheckResult(
                category=HealthCategory.CONFIGURATION,
                component="config_version",
                status="UP",
                latency_ms=latency,
                message="Version compatibility verified.",
            ))
        except ValueError as e:
            raise GrowthScoutRuntimeError(
                error_code=RuntimeErrorCode.CONFIGURATION_ERROR,
                message=f"Invalid version format: {str(e)}",
                service=None,
                retryable=False,
            )

        # 2. Check Google Maps API Key
        start_time = time.perf_counter()
        if not self.config.google_maps_api_key:
            latency = (time.perf_counter() - start_time) * 1000.0
            results.append(HealthCheckResult(
                category=HealthCategory.AUTHENTICATION,
                component="google_maps_api_key",
                status="DOWN",
                latency_ms=latency,
                message="GOOGLE_MAPS_API_KEY is not configured.",
                error_code=RuntimeErrorCode.CONFIGURATION_ERROR
            ))
        else:
            latency = (time.perf_counter() - start_time) * 1000.0
            results.append(HealthCheckResult(
                category=HealthCategory.AUTHENTICATION,
                component="google_maps_api_key",
                status="UP",
                latency_ms=latency,
                message="GOOGLE_MAPS_API_KEY configuration verified.",
            ))

        # 3. Check Gemini API Key
        start_time = time.perf_counter()
        if not self.config.gemini_api_key:
            latency = (time.perf_counter() - start_time) * 1000.0
            results.append(HealthCheckResult(
                category=HealthCategory.AUTHENTICATION,
                component="gemini_api_key",
                status="DOWN",
                latency_ms=latency,
                message="GEMINI_API_KEY is not configured.",
                error_code=RuntimeErrorCode.CONFIGURATION_ERROR
            ))
        else:
            latency = (time.perf_counter() - start_time) * 1000.0
            results.append(HealthCheckResult(
                category=HealthCategory.AUTHENTICATION,
                component="gemini_api_key",
                status="UP",
                latency_ms=latency,
                message="GEMINI_API_KEY configuration verified.",
            ))

        # 4. Dry-run MCP servers
        for server_name, server_module in [
            ("local_search_server", "servers.local_search_server.server"),
            ("web_analyzer_server", "servers.web_analyzer_server.server")
        ]:
            start_time = time.perf_counter()
            try:
                env = dict(os.environ)
                env["GOOGLE_MAPS_API_KEY"] = self.config.google_maps_api_key
                env["GEMINI_API_KEY"] = self.config.gemini_api_key
                
                module_path = server_module.replace(".", "/") + ".py"
                if not os.path.exists(module_path):
                    raise FileNotFoundError(f"Server module file not found: {module_path}")

                process = await asyncio.create_subprocess_exec(
                    "python", "-m", server_module,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                
                try:
                    await asyncio.wait_for(process.wait(), timeout=0.6)
                    if process.returncode != 0:
                        stderr_bytes = await process.stderr.read() if process.stderr else b""
                        stderr_str = stderr_bytes.decode().strip()
                        raise RuntimeError(f"Server exited with code {process.returncode}: {stderr_str}")
                    else:
                        raise RuntimeError("Server exited immediately with code 0 (expected stdio loop to keep running).")
                except asyncio.TimeoutError:
                    try:
                        process.terminate()
                        await process.wait()
                    except Exception:
                        pass
                
                latency = (time.perf_counter() - start_time) * 1000.0
                results.append(HealthCheckResult(
                    category=HealthCategory.DEPENDENCIES,
                    component=server_name,
                    status="UP",
                    latency_ms=latency,
                    message="FastMCP server startup verified.",
                ))
            except Exception as e:
                latency = (time.perf_counter() - start_time) * 1000.0
                results.append(HealthCheckResult(
                    category=HealthCategory.DEPENDENCIES,
                    component=server_name,
                    status="DOWN",
                    latency_ms=latency,
                    message=f"FastMCP server startup verification failed: {str(e)}",
                    error_code=RuntimeErrorCode.SUBPROCESS_ERROR
                ))

        return results
