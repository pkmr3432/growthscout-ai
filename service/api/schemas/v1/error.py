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

class StandardErrorResponse(BaseModel):
    error: ErrorDetail = Field(..., description="Wrapped error details payload")
