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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "niche": "dental clinic",
                    "location": "Boston, MA",
                    "max_leads": 10
                }
            ]
        }
    }

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

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "session_id": "sess_a1b2c3d4",
                    "workflow_id": "wf_z9y8x7w6",
                    "current_state": "idle",
                    "niche": "dental clinic",
                    "location": "Boston, MA",
                    "max_leads": 10,
                    "revision_count": 0,
                    "created_at": "2026-06-27T22:39:22Z",
                    "updated_at": "2026-06-27T22:39:22Z",
                    "status": "idle"
                }
            ]
        }
    }

class FeedbackSubmitRequest(BaseModel):
    approved: bool = Field(..., description="True to approve work and advance; False to request revision")
    feedback_notes: Optional[str] = Field(None, max_length=500, description="Human reviewer notes/instructions")
    adjusted_data: Optional[Dict[str, Any]] = Field(None, description="Optional modifications to case data")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "approved": True,
                    "feedback_notes": "Leads look good, proceed to next step.",
                    "adjusted_data": None
                }
            ]
        }
    }
