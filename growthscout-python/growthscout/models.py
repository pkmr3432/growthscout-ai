# growthscout-python/growthscout/models.py
"""
Typed data models for the GrowthScout AI Python SDK.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    niche: str
    location: str
    max_leads: int = 5


class SessionResponse(BaseModel):
    session_id: str
    workflow_id: str
    current_state: str
    niche: str
    location: str
    max_leads: int
    revision_count: int
    created_at: datetime
    updated_at: datetime
    status: str


class FeedbackSubmitRequest(BaseModel):
    approved: bool
    feedback_notes: Optional[str] = None
    adjusted_data: Optional[Dict[str, Any]] = None


class EventEnvelope(BaseModel):
    event_id: int
    event_type: str
    session_id: str
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
