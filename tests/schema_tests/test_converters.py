import json
import pytest
from datetime import datetime, timezone
from utils.schema_integration.models import (
    SessionLead, AuditHistory, OpportunityHistory, ClassifiedOpportunity, BusinessImpact
)
from utils.schema_integration.converters import (
    convert_discovery_to_leads, convert_audit_to_history, convert_opportunity_to_prompt
)
from utils.schema_integration.serialization import (
    serialize_model, deserialize_model
)

def test_convert_discovery_to_leads():
    mock_discovery = {
        "results": [
            {
                "name": "Austin Dentistry",
                "formatted_address": "120 Congress Ave, Austin, TX",
                "website": "https://austindentistry.com",
                "rating": 4.5,
                "user_ratings_total": 45
            },
            {
                "name": "No Web Chiropractor",
                "formatted_address": "400 Main St, Austin, TX",
                "website": None,
                "rating": 3.8,
                "user_ratings_total": 12
            }
        ]
    }
    
    leads = convert_discovery_to_leads(mock_discovery)
    assert len(leads) == 2
    
    assert leads[0].business_name == "Austin Dentistry"
    assert leads[0].website_status == "Modern Website"
    assert leads[1].business_name == "No Web Chiropractor"
    assert leads[1].website_status == "No Website"

def test_convert_audit_to_history():
    biz_id = "biz_a1b2c3d4"
    fetcher_out = {
        "url": "https://austindentistry.com",
        "status": 200,
        "content": "<html></html>"
    }
    scanner_out = {
        "cms": "wordpress",
        "load_time_seconds": 1.34,
        "has_booking_widget": True
    }
    auditor_out = {
        "seo_data": {
            "meta_title": "Austin Dentistry - Dentist Austin",
            "meta_description": "Dentistry clinic in Austin",
            "h1_elements": ["Austin Dentistry"],
            "has_schema_markup": True
        }
    }
    
    audit = convert_audit_to_history(biz_id, fetcher_out, scanner_out, auditor_out)
    
    assert audit.business_id == biz_id
    assert audit.audit_id.startswith("aud_")
    assert audit.cms == "wordpress"
    assert audit.load_time_seconds == 1.34
    assert audit.has_booking_widget is True
    assert audit.seo_data.meta_title == "Austin Dentistry - Dentist Austin"
    assert audit.seo_data.has_schema_markup is True

def test_convert_opportunity_to_prompt():
    # Setup dummy AuditHistory
    biz_id = "biz_a1b2c3d4"
    fetcher_out = {
        "url": "https://austindentistry.com",
        "status": 200,
        "content": "<html></html>"
    }
    scanner_out = {
        "cms": "wordpress",
        "load_time_seconds": 1.34,
        "has_booking_widget": True
    }
    auditor_out = {
        "seo_data": {
            "meta_title": "Austin Title",
            "meta_description": "Austin Desc",
            "h1_elements": [],
            "has_schema_markup": False
        }
    }
    audit = convert_audit_to_history(biz_id, fetcher_out, scanner_out, auditor_out)
    
    # Setup dummy OpportunityHistory
    opp = OpportunityHistory(
        opportunity_id="opp_1a2b3c4d",
        business_id=biz_id,
        opportunity_score=85,
        confidence_score="High",
        confidence_reasoning="Crawl complete",
        classified_opportunities=[
            ClassifiedOpportunity(category="SEO", urgency="High")
        ],
        business_impacts=[
            BusinessImpact(technical_finding="Missing Schema", business_consequence="Lower search rankings")
        ],
        created_at=datetime.now(timezone.utc)
    )
    
    prompt_vars = convert_opportunity_to_prompt(audit, opp)
    
    assert prompt_vars["opportunity_score"] == 85
    assert prompt_vars["confidence_score"] == "High"
    assert len(prompt_vars["technical_gaps"]) == 1
    assert prompt_vars["technical_gaps"][0]["category"] == "SEO"
    assert prompt_vars["cms"] == "wordpress"

def test_serialization_loop():
    lead = SessionLead(
        business_name="Austin Dental",
        address="Austin",
        website_url="https://austindental.com",
        website_status="Modern Website",
        google_rating=4.5,
        review_count=12
    )
    
    json_str = serialize_model(lead)
    deserialized = deserialize_model(SessionLead, json_str)
    
    assert deserialized.business_name == lead.business_name
    assert deserialized.google_rating == lead.google_rating
