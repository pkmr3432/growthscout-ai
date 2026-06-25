from typing import List, Optional
from pydantic import BaseModel, Field

# --- Shared Sub-models ---

class DiscoveryLead(BaseModel):
    business_name: str = Field(..., description="The official name of the local business.")
    address: str = Field(..., description="The formatted physical address of the business.")
    website_url: Optional[str] = Field(None, description="The resolved website URL, or null if not found.")
    website_status: str = Field(..., description="Status category: 'No Website', 'Outdated Website', or 'Modern Website'.")
    google_rating: Optional[float] = Field(None, description="Google Maps average user rating.")
    review_count: Optional[int] = Field(None, description="Total Google Maps review counts.")
    google_maps_place_id: Optional[str] = Field(None, description="Google Maps unique place ID.")

class AuditSeoData(BaseModel):
    meta_title: Optional[str] = Field(None, description="The parsed meta title tag content.")
    meta_description: Optional[str] = Field(None, description="The parsed meta description tag content.")
    h1_elements: List[str] = Field(default=[], description="List of H1 heading texts parsed from the page.")
    has_schema_markup: bool = Field(..., description="True if schema/microdata markup was detected.")

class AuditResults(BaseModel):
    website_url: str = Field(..., description="The target website URL scanned.")
    http_status_code: int = Field(..., description="The HTTP status response code of the fetch request.")
    cms: str = Field(..., description="The CMS platform or UI framework detected (e.g. wordpress, wix, next.js).")
    load_time_seconds: float = Field(..., description="Webpage load time in seconds.")
    has_booking_widget: bool = Field(..., description="True if booking/scheduling widget was found.")
    seo_data: AuditSeoData = Field(..., description="Structured SEO metadata parsed from page.")

class OpportunityClassified(BaseModel):
    category: str = Field(..., description="One of the 8 Opportunity Categories.")
    urgency: str = Field(..., description="The urgency classification level (High, Medium, Low).")

class OpportunityImpact(BaseModel):
    technical_finding: str = Field(..., description="The specific technical presence flaw detected.")
    business_consequence: str = Field(..., description="The translation of the flaw into a business risk/outcome.")

class CompetitorProfile(BaseModel):
    business_name: str = Field(..., description="The name of the competitor business.")
    website_url: Optional[str] = Field(None, description="Website URL of the competitor.")
    google_rating: Optional[float] = Field(None, description="Google Maps rating of the competitor.")
    review_count: Optional[int] = Field(None, description="Review count of the competitor.")

class CategoryScores(BaseModel):
    no_website: Optional[int] = Field(None, description="Score for the No Website category.")
    website_modernization: Optional[int] = Field(None, description="Score for the Website Modernization category.")
    seo: Optional[int] = Field(None, description="Score for the SEO category.")
    performance: Optional[int] = Field(None, description="Score for the Performance category.")
    conversion_optimization: Optional[int] = Field(None, description="Score for the Conversion Optimization category.")
    analytics: Optional[int] = Field(None, description="Score for the Analytics category.")
    reputation: Optional[int] = Field(None, description="Score for the Reputation category.")
    competitive_positioning: Optional[int] = Field(None, description="Score for the Competitive Positioning category.")

# --- Primary Worker Output Schemas ---

class DiscoveryLeadsSchema(BaseModel):
    leads: List[DiscoveryLead] = Field(..., description="List of discovered local business target leads.")
    competitor_candidates: List[DiscoveryLead] = Field(..., description="List of competitor candidate profiles.")

class AuditResultsSchema(BaseModel):
    audit_results: AuditResults = Field(..., description="Structured technical presence audit metrics.")

class OpportunityAnalysisSchema(BaseModel):
    opportunities: List[str] = Field(..., description="List of opportunity category names identified.")
    lead_score: int = Field(..., description="Overall calculated lead opportunity score (0 to 100).")
    competitor_profiles: List[CompetitorProfile] = Field(default=[], description="Benchmarks comparison statistics against local competitors.")
    opportunity_scores: CategoryScores = Field(..., description="Broken down opportunity scores for specific categories.")
    business_impact_analysis: List[OpportunityImpact] = Field(..., description="Mappings connecting technical findings to business outcomes.")
    opportunity_summary: str = Field(..., description="Executive narrative summary of scores and gaps.")

class GrowthReportsSchema(BaseModel):
    growth_report_markdown: str = Field(..., description="The primary compiled Growth Intelligence Report written in Markdown.")
    email_draft: Optional[str] = Field(None, description="Optional consultative cold outreach email draft matching the AIDA structure.")
    proposal_markdown: Optional[str] = Field(None, description="Optional derived business proposal pitch copy.")
