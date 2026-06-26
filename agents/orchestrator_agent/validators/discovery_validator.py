# agents/orchestrator_agent/validators/discovery_validator.py
"""
Discovery Worker validator implementation.
"""
from typing import Any, List, Optional, Type
from pydantic import BaseModel

from agents.shared.schemas import DiscoveryLeadsSchema, DiscoveryLead
from .common import BaseValidator, ValidationResult
from .schema_validator import SchemaValidator

def normalize_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    url = url.strip()
    if url.endswith("/"):
        url = url[:-1]
    if "://" in url:
        parts = url.split("://", 1)
        scheme = parts[0].lower()
        rest = parts[1]
        if "/" in rest:
            domain, path = rest.split("/", 1)
            url = f"{scheme}://{domain.lower()}/{path}"
        else:
            url = f"{scheme}://{rest.lower()}"
    else:
        url = url.lower()
    return url


class DiscoveryValidator(BaseValidator):
    """
    Validator for business_discovery_agent output (DiscoveryLeadsSchema).
    """

    def validate(self, raw_output: Any, output_schema: Type[BaseModel]) -> ValidationResult:
        # 1. Schema Validation
        schema_result = SchemaValidator().validate(raw_output, output_schema)
        if not schema_result.valid:
            return schema_result

        model: DiscoveryLeadsSchema = schema_result.normalized_output  # type: ignore[assignment]
        
        errors: List[str] = []
        warnings: List[str] = []

        # 2. Business Validation
        # Check duplicate business names & place IDs
        seen_lead_names = set()
        seen_lead_places = set()
        for lead in model.leads:
            name = lead.business_name.strip()
            if name in seen_lead_names:
                errors.append(f"Duplicate business name found in leads: '{name}'")
            seen_lead_names.add(name)

            if lead.google_maps_place_id:
                place_id = lead.google_maps_place_id.strip()
                if place_id in seen_lead_places:
                    errors.append(f"Duplicate place ID found in leads: '{place_id}'")
                seen_lead_places.add(place_id)

        seen_comp_names = set()
        seen_comp_places = set()
        for comp in model.competitor_candidates:
            name = comp.business_name.strip()
            if name in seen_comp_names:
                errors.append(f"Duplicate business name found in competitor candidates: '{name}'")
            seen_comp_names.add(name)

            if comp.google_maps_place_id:
                place_id = comp.google_maps_place_id.strip()
                if place_id in seen_comp_places:
                    errors.append(f"Duplicate place ID found in competitor candidates: '{place_id}'")
                seen_comp_places.add(place_id)

        # Check duplicate URLs
        seen_lead_urls = set()
        for lead in model.leads:
            if lead.website_url:
                norm_u = normalize_url(lead.website_url)
                if norm_u in seen_lead_urls:
                    errors.append(f"Duplicate website URL found in leads: '{lead.website_url}'")
                seen_lead_urls.add(norm_u)

        seen_comp_urls = set()
        for comp in model.competitor_candidates:
            if comp.website_url:
                norm_u = normalize_url(comp.website_url)
                if norm_u in seen_comp_urls:
                    errors.append(f"Duplicate website URL found in competitor candidates: '{comp.website_url}'")
                seen_comp_urls.add(norm_u)

        # 3. Evidence Validation
        for idx, lead in enumerate(model.leads):
            if not lead.business_name.strip():
                errors.append(f"Lead at index {idx} has an empty business name.")
            if not lead.address.strip():
                errors.append(f"Lead '{lead.business_name}' has an empty physical address.")

        for idx, comp in enumerate(model.competitor_candidates):
            if not comp.business_name.strip():
                errors.append(f"Competitor at index {idx} has an empty business name.")

        # If business or evidence validation failed, return invalid result
        if errors:
            return ValidationResult(
                valid=False,
                normalized_output=None,
                errors=errors,
                warnings=warnings,
                metrics={},
                evidence_summary=""
            )

        # 4. Normalization (Idempotent)
        normalized_leads = []
        for lead in model.leads:
            normalized_leads.append(DiscoveryLead(
                business_name=lead.business_name.strip(),
                address=lead.address.strip(),
                website_url=normalize_url(lead.website_url),
                website_status=lead.website_status.strip(),
                google_rating=lead.google_rating,
                review_count=lead.review_count,
                google_maps_place_id=lead.google_maps_place_id.strip() if lead.google_maps_place_id else None
            ))

        normalized_competitors = []
        for comp in model.competitor_candidates:
            normalized_competitors.append(DiscoveryLead(
                business_name=comp.business_name.strip(),
                address=comp.address.strip(),
                website_url=normalize_url(comp.website_url),
                website_status=comp.website_status.strip(),
                google_rating=comp.google_rating,
                review_count=comp.review_count,
                google_maps_place_id=comp.google_maps_place_id.strip() if comp.google_maps_place_id else None
            ))

        normalized_model = DiscoveryLeadsSchema(
            leads=normalized_leads,
            competitor_candidates=normalized_competitors
        )

        evidence_summary = f"Discovered {len(normalized_leads)} leads and {len(normalized_competitors)} competitor candidates."

        return ValidationResult(
            valid=True,
            normalized_output=normalized_model,
            errors=[],
            warnings=warnings,
            metrics={},
            evidence_summary=evidence_summary
        )
