# agents/orchestrator_agent/validators/website_validator.py
"""
Website Analysis Worker validator implementation.
"""
from typing import Any, List, Type
from pydantic import BaseModel

from agents.shared.schemas import AuditResultsSchema, AuditResults, AuditSeoData
from .common import BaseValidator, ValidationResult
from .schema_validator import SchemaValidator
from .discovery_validator import normalize_url

class WebsiteValidator(BaseValidator):
    """
    Validator for website_analysis_agent output (AuditResultsSchema).
    """

    def validate(self, raw_output: Any, output_schema: Type[BaseModel]) -> ValidationResult:
        # 1. Schema Validation
        schema_result = SchemaValidator().validate(raw_output, output_schema)
        if not schema_result.valid:
            return schema_result

        model: AuditResultsSchema = schema_result.normalized_output  # type: ignore[assignment]
        audit = model.audit_results

        errors: List[str] = []
        warnings: List[str] = []

        # 2. Business Validation
        # Check HTTP status codes (must be 100-599)
        if not (100 <= audit.http_status_code <= 599):
            errors.append(f"HTTP status code {audit.http_status_code} is out of valid range [100, 599]")

        # Check load time (must be non-negative)
        if audit.load_time_seconds < 0.0:
            errors.append(f"Load time {audit.load_time_seconds} must be non-negative")

        # 3. Evidence Validation
        if not audit.website_url.strip():
            errors.append("Website URL must not be empty.")

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
        normalized_seo = AuditSeoData(
            meta_title=audit.seo_data.meta_title.strip() if audit.seo_data.meta_title else None,
            meta_description=audit.seo_data.meta_description.strip() if audit.seo_data.meta_description else None,
            h1_elements=[h.strip() for h in audit.seo_data.h1_elements],
            has_schema_markup=audit.seo_data.has_schema_markup
        )

        normalized_audit = AuditResults(
            website_url=normalize_url(audit.website_url),  # type: ignore[arg-type]
            http_status_code=audit.http_status_code,
            cms=audit.cms.strip().lower(),  # lowercase CMS names
            load_time_seconds=audit.load_time_seconds,
            has_booking_widget=audit.has_booking_widget,
            seo_data=normalized_seo
        )

        normalized_model = AuditResultsSchema(audit_results=normalized_audit)
        evidence_summary = f"Audited {normalized_audit.website_url} (CMS: {normalized_audit.cms}, HTTP: {normalized_audit.http_status_code})"

        return ValidationResult(
            valid=True,
            normalized_output=normalized_model,
            errors=[],
            warnings=warnings,
            metrics={},
            evidence_summary=evidence_summary
        )
