# agents/orchestrator_agent/error_codes.py
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from .service_names import ServiceName

class RuntimeErrorCode(str, Enum):
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    SUBPROCESS_ERROR = "SUBPROCESS_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNEXPECTED_ERROR = "UNEXPECTED_ERROR"
    COST_THRESHOLD_EXCEEDED = "COST_THRESHOLD_EXCEEDED"

class GrowthScoutRuntimeError(Exception):
    def __init__(
        self,
        error_code: RuntimeErrorCode,
        message: str,
        service: Optional[Any] = None,
        retryable: bool = False,
        correlation_id: Optional[str] = None,
        original_exception: Optional[Any] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        
        # Coerce string to ServiceName if appropriate
        if isinstance(service, str):
            try:
                service = ServiceName(service)
            except ValueError:
                try:
                    service = ServiceName(service.upper())
                except ValueError:
                    pass
                    
        self.service = service
        self.retryable = retryable
        self.correlation_id = correlation_id
        self.original_exception = original_exception
        self.timestamp = timestamp or datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "service": self.service.value if hasattr(self.service, "value") else self.service,
            "retryable": self.retryable,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "original_exception": str(self.original_exception) if self.original_exception else None,
        }
