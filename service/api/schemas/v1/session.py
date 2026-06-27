# service/api/schemas/v1/session.py
"""
Pydantic API request and response models for Session operations in v1.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class SessionCreateRequest(BaseModel):
    niche: str = Field(..., min_length=2, max_length=50, description="Business vertical (e.g. 'HVAC repair')")
    location: str = Field(..., min_length=2, max_length=100, description="Target location (e.g. 'Austin, TX')")
    max_leads: int = Field(default=5, ge=1, le=50, description="Maximum number of leads to scan")

class SessionResponse(BaseModel):
    session_id: str = Field(..., description="Unique session identifier (sess_[hex8])")
    workflow_id: str = Field(..., description="Unique workflow run identifier (wf_[hex8])")
    current_state: str = Field(..., description="Active workflow state in the orchestrator")
    niche: str = Field(..., description="Target business niche")
    location: str = Field(..., description="Target city/state")
    max_leads: int = Field(..., description="Maximum leads count limit")
    revision_count: int = Field(..., description="HITL revision cycle count")
    created_at: datetime = Field(..., description="Creation UTC timestamp")
    updated_at: datetime = Field(..., description="Last updated UTC timestamp")
    status: str = Field(default="idle", description="Execution status: idle, running, paused_on_gate, completed, failed")

class FeedbackSubmitRequest(BaseModel):
    approved: bool = Field(..., description="True to approve work and advance; False to request revision")
    feedback_notes: Optional[str] = Field(None, max_length=500, description="Human reviewer notes/instructions")
    adjusted_data: Optional[Dict[str, Any]] = Field(None, description="Optional modifications to case data")
