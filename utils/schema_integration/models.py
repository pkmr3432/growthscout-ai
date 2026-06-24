from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

# --- Session Memory Sub-models ---

class QueryContext(BaseModel):
    niche: str
    location: str
    max_leads: int = 5

class SessionLead(BaseModel):
    business_name: str
    address: str
    website_url: Optional[str] = None
    website_status: str  # "No Website" | "Outdated Website" | "Modern Website"
    google_rating: Optional[float] = None
    review_count: Optional[int] = None

class SessionMemory(BaseModel):
    session_id: str = Field(..., pattern="^sess_[a-f0-9]{8}$")
    status: str
    created_at: datetime
    updated_at: datetime
    query_context: QueryContext
    leads: List[SessionLead] = []

# --- Business Profile Models ---

class MapsMetadata(BaseModel):
    google_rating: Optional[float] = None
    review_count: Optional[int] = None
    google_maps_place_id: Optional[str] = None

class BusinessProfile(BaseModel):
    business_id: str = Field(..., pattern="^biz_[a-f0-9]{8}$")
    business_name: str
    website_url: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    maps_metadata: MapsMetadata
    last_audited_at: datetime

# --- Audit History Models ---

class SeoDataModel(BaseModel):
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    h1_elements: List[str] = []
    has_schema_markup: bool = False

class AuditHistory(BaseModel):
    audit_id: str = Field(..., pattern="^aud_[a-f0-9]{8}$")
    business_id: str = Field(..., pattern="^biz_[a-f0-9]{8}$")
    website_url: Optional[str] = None
    http_status_code: int
    raw_html: Optional[str] = None
    cms: str = "custom"
    load_time_seconds: float
    has_booking_widget: bool = False
    seo_data: SeoDataModel
    created_at: datetime

# --- Opportunity History Models ---

class ClassifiedOpportunity(BaseModel):
    category: str
    urgency: str

class BusinessImpact(BaseModel):
    technical_finding: str
    business_consequence: str

class OpportunityHistory(BaseModel):
    opportunity_id: str = Field(..., pattern="^opp_[a-f0-9]{8}$")
    business_id: str = Field(..., pattern="^biz_[a-f0-9]{8}$")
    opportunity_score: int
    confidence_score: str
    confidence_reasoning: str
    classified_opportunities: List[ClassifiedOpportunity]
    business_impacts: List[BusinessImpact]
    created_at: datetime

# --- Growth Reports Models ---

class GrowthReport(BaseModel):
    report_id: str = Field(..., pattern="^rep_[a-f0-9]{8}$")
    business_id: str = Field(..., pattern="^biz_[a-f0-9]{8}$")
    version: str = "v1"
    growth_report_markdown: str
    email_draft: Optional[str] = None
    linkedin_message: Optional[str] = None
    created_at: datetime
