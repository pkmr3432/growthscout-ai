from typing import List, Dict, Any
from datetime import datetime, timezone
import uuid
from utils.schema_integration.models import (
    SessionLead, AuditHistory, SeoDataModel, OpportunityHistory, ClassifiedOpportunity, BusinessImpact
)

def convert_discovery_to_leads(discovery_results: Dict[str, Any]) -> List[SessionLead]:
    """Converts local_business_search raw tool outputs into SessionLead model objects."""
    leads = []
    results = discovery_results.get("results", [])
    
    for result in results:
        website_url = result.get("website")
        
        # Simple web existence classification heuristic
        if not website_url:
            website_status = "No Website"
        else:
            # Placeholder: defaults to Outdated for ratings below 4.0
            rating = result.get("rating")
            if rating and rating < 4.0:
                website_status = "Outdated Website"
            else:
                website_status = "Modern Website"
                
        lead = SessionLead(
            business_name=result.get("name", ""),
            address=result.get("formatted_address", ""),
            website_url=website_url,
            website_status=website_status,
            google_rating=result.get("rating"),
            review_count=result.get("user_ratings_total")
        )
        leads.append(lead)
        
    return leads

def convert_audit_to_history(
    business_id: str, 
    fetcher_output: Dict[str, Any], 
    scanner_output: Dict[str, Any], 
    auditor_output: Dict[str, Any]
) -> AuditHistory:
    """Merges three independent web analyzer tool results into a single AuditHistory database record."""
    seo_raw = auditor_output.get("seo_data", {})
    seo_data = SeoDataModel(
        meta_title=seo_raw.get("meta_title"),
        meta_description=seo_raw.get("meta_description"),
        h1_elements=seo_raw.get("h1_elements", []),
        has_schema_markup=seo_raw.get("has_schema_markup", False)
    )
    
    # Generate unique 8-character hex audit_id
    audit_id = f"aud_{uuid.uuid4().hex[:8]}"
    
    return AuditHistory(
        audit_id=audit_id,
        business_id=business_id,
        website_url=fetcher_output.get("url"),
        http_status_code=fetcher_output.get("status", 200),
        raw_html=fetcher_output.get("content"),
        cms=scanner_output.get("cms", "custom"),
        load_time_seconds=scanner_output.get("load_time_seconds", 0.0),
        has_booking_widget=scanner_output.get("has_booking_widget", False),
        seo_data=seo_data,
        created_at=datetime.now(timezone.utc)
    )

def convert_opportunity_to_prompt(audit: AuditHistory, opp: OpportunityHistory) -> Dict[str, Any]:
    """Compiles unified prompt variables required by the growth-report-generation skill."""
    return {
        "business_name": audit.website_url or "Local Business",
        "opportunity_score": opp.opportunity_score,
        "confidence_score": opp.confidence_score,
        "confidence_reasoning": opp.confidence_reasoning,
        "technical_gaps": [
            {
                "category": item.category,
                "urgency": item.urgency
            }
            for item in opp.classified_opportunities
        ],
        "business_consequences": [
            {
                "technical_finding": item.technical_finding,
                "business_consequence": item.business_consequence
            }
            for item in opp.business_impacts
        ],
        "cms": audit.cms,
        "load_time_seconds": audit.load_time_seconds,
        "has_booking_widget": audit.has_booking_widget,
        "has_schema_markup": audit.seo_data.has_schema_markup
    }
