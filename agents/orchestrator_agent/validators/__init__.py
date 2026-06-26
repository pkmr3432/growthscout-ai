# agents/orchestrator_agent/validators/__init__.py
"""
Central Validation Pipeline module.
"""
import time
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from .common import ValidationResult, BaseValidator
from .schema_validator import SchemaValidator
from .discovery_validator import DiscoveryValidator
from .website_validator import WebsiteValidator
from .opportunity_validator import OpportunityValidator
from .report_validator import ReportValidator

class ValidationPipeline:
    """
    Central Validation Pipeline that coordinates worker-specific validators
    and enforces the order:
    1. Schema Validation
    2. Business Validation
    3. Evidence Validation
    4. Normalization
    """

    def __init__(self) -> None:
        self._validators: Dict[str, BaseValidator] = {
            "business_discovery_agent": DiscoveryValidator(),
            "website_analysis_agent": WebsiteValidator(),
            "opportunity_agent": OpportunityValidator(),
            "growth_intelligence_agent": ReportValidator(),
        }

    def validate(self, worker_name: str, raw_output: Any, output_schema: Type[BaseModel]) -> ValidationResult:
        """
        Validate raw output for the given worker against the expected schema.

        Executes validation, handles schema/business/evidence layers, normalized output,
        and computes metrics (duration, failure types).
        """
        start_time = time.perf_counter()

        validator = self._validators.get(worker_name)
        if not validator:
            validator = SchemaValidator()

        # Execute validator (this executes Schema, Business, Evidence, and Normalization in order)
        res = validator.validate(raw_output, output_schema)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Classify failure type for metrics
        failure_type: Optional[str] = None
        if not res.valid:
            # Re-check with schema validator to isolate schema failure from business/evidence failures
            schema_check = SchemaValidator().validate(raw_output, output_schema)
            if not schema_check.valid:
                failure_type = "schema"
            else:
                failure_type = "business"

        metrics = {
            "validation_duration_ms": duration_ms,
            "validator_name": validator.__class__.__name__,
            "worker_name": worker_name,
            "warnings_count": len(res.warnings),
            "normalized": res.valid and res.normalized_output is not None,
            "failure_type": failure_type,
        }

        return ValidationResult(
            valid=res.valid,
            normalized_output=res.normalized_output,
            warnings=res.warnings,
            errors=res.errors,
            metrics=metrics,
            evidence_summary=res.evidence_summary
        )
