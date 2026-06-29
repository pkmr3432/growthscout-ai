# service/api/schemas/v1/error.py
"""
Pydantic schemas for standardized API JSON error formats.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    code: str = Field(..., description="System-specific standardized error code")
    message: str = Field(..., description="User-friendly error explanation")
    request_id: str = Field(..., description="Unique HTTP request trace ID")
    correlation_id: str = Field(..., description="Correlation ID tying logs together")
    timestamp: datetime = Field(..., description="UTC timestamp of the error event")
    retryable: bool = Field(default=False, description="True if client should attempt request retry")
    details: Optional[Dict[str, Any]] = Field(None, description="Optional extra key-value diagnostic metadata")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "code": "SESSION_LOCKED",
                    "message": "Session 'sess_123' is currently running an active background task.",
                    "request_id": "req_5a6b7c8d",
                    "correlation_id": "corr_9e8f7d6c",
                    "timestamp": "2026-06-27T22:39:22Z",
                    "retryable": False,
                    "details": {
                        "session_id": "sess_123"
                    }
                }
            ]
        }
    }

class StandardErrorResponse(BaseModel):
    error: ErrorDetail = Field(..., description="Wrapped error details payload")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": {
                        "code": "SESSION_LOCKED",
                        "message": "Session 'sess_123' is currently running an active background task.",
                        "request_id": "req_5a6b7c8d",
                        "correlation_id": "corr_9e8f7d6c",
                        "timestamp": "2026-06-27T22:39:22Z",
                        "retryable": False,
                        "details": {
                            "session_id": "sess_123"
                        }
                    }
                }
            ]
        }
    }
