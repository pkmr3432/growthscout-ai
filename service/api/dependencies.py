# service/api/dependencies.py
"""
FastAPI dependency providers for service registry and auth security.
"""

from fastapi import Depends, Header, HTTPException, status
from service.infrastructure.config import ServiceSettings
from service.infrastructure.registry import ServiceRegistry, registry
from service.application.authenticator import Authenticator

def get_registry() -> ServiceRegistry:
    """Returns the wired service registry singleton."""
    return registry

def get_settings(reg: ServiceRegistry = Depends(get_registry)) -> ServiceSettings:
    """Returns application configuration settings."""
    return reg.settings

def get_authenticator(reg: ServiceRegistry = Depends(get_registry)) -> Authenticator:
    """Returns authenticator service abstraction."""
    return reg.authenticator

async def verify_api_key(
    x_api_key: str = Header(..., description="Authentication client API key"),
    authenticator: Authenticator = Depends(get_authenticator)
) -> str:
    """
    Enforces X-API-Key header authentication check.
    Raises 401 on authentication failures.
    """
    is_valid = await authenticator.authenticate(x_api_key)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "AUTHENTICATION_FAILED",
                    "message": "Invalid or missing X-API-Key authentication header."
                }
            }
        )
    return x_api_key

_execution_service = None

def get_execution_service() -> ExecutionService:
    """Returns ExecutionService application coordinator singleton."""
    global _execution_service
    if _execution_service is None:
        from service.application.execution_service import ExecutionService
        _execution_service = ExecutionService()
    return _execution_service

