# agents/orchestrator_agent/validators/common.py
"""
Common types and interface for orchestrator validators.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field

class ValidationResult(BaseModel):
    """
    Standardized immutable ValidationResult model.
    """
    model_config = {"frozen": True}

    valid: bool = Field(..., description="True if output is completely valid and normalized.")
    normalized_output: Optional[BaseModel] = Field(None, description="The normalized output BaseModel instance, or None.")
    warnings: List[str] = Field(default_factory=list, description="Warnings generated during validation/normalization.")
    errors: List[str] = Field(default_factory=list, description="List of schema, business, or evidence validation errors.")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Metrics recorded during validation (e.g. duration_ms).")
    evidence_summary: str = Field(default="", description="Summary of evidence validated.")


class BaseValidator(ABC):
    """
    Common validation interface that all dedicated validators must inherit from.
    """
    @abstractmethod
    def validate(self, raw_output: Any, output_schema: Type[BaseModel]) -> ValidationResult:
        """
        Validate and normalize the raw worker output against a given output schema.

        Args:
            raw_output: The raw output from worker execution (can be BaseModel, dict, or str).
            output_schema: The expected Pydantic model class.

        Returns:
            ValidationResult containing status, errors, warnings, and normalized model.
        """
        pass
