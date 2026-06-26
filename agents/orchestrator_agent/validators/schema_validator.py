# agents/orchestrator_agent/validators/schema_validator.py
"""
Schema-level validation implementation.
"""
import json
from typing import Any, List, Optional, Type
from pydantic import BaseModel, ValidationError

from .common import BaseValidator, ValidationResult

def extract_balanced_json(text: str) -> Optional[str]:
    """
    Locates the first '{' and finds its matching balanced '}'.
    Ignores braces inside double quotes, handling escaped quotes.
    Returns the JSON string or None if not found or unbalanced.
    """
    start_idx = text.find('{')
    if start_idx == -1:
        return None
        
    brace_count = 0
    in_quote = False
    escaped = False
    
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if escaped:
            escaped = False
            continue
            
        if char == '\\':
            escaped = True
            continue
            
        if char == '"':
            in_quote = not in_quote
            continue
            
        if not in_quote:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    return text[start_idx:i+1]
                    
    return None


class SchemaValidator(BaseValidator):
    """
    Validates output conforming to a Pydantic BaseModel.
    """

    def validate(self, raw_output: Any, output_schema: Type[BaseModel]) -> ValidationResult:
        errors: List[str] = []
        parsed_dict: Optional[dict] = None
        normalized_output: Optional[BaseModel] = None

        if isinstance(raw_output, BaseModel):
            # Already a BaseModel, re-validate to ensure model conformance and extract any errors
            try:
                # Use model_dump to get a dictionary of standard python types
                data = raw_output.model_dump()
                normalized_output = output_schema.model_validate(data)
            except ValidationError as e:
                errors.extend(self._format_validation_errors(e))
            except Exception as e:
                errors.append(f"Unexpected validation error: {str(e)}")

        elif isinstance(raw_output, dict):
            try:
                normalized_output = output_schema.model_validate(raw_output)
            except ValidationError as e:
                errors.extend(self._format_validation_errors(e))
            except Exception as e:
                errors.append(f"Unexpected validation error: {str(e)}")

        elif isinstance(raw_output, str):
            json_str = extract_balanced_json(raw_output)
            if json_str:
                try:
                    data = json.loads(json_str)
                    normalized_output = output_schema.model_validate(data)
                except json.JSONDecodeError as e:
                    errors.append(f"JSON structure invalid: {str(e)}")
                except ValidationError as e:
                    errors.extend(self._format_validation_errors(e))
                except Exception as e:
                    errors.append(f"Unexpected validation error: {str(e)}")
            else:
                errors.append("No balanced JSON object found in string output.")

        else:
            errors.append(f"Unsupported raw output type: {type(raw_output).__name__}")

        valid = len(errors) == 0
        return ValidationResult(
            valid=valid,
            normalized_output=normalized_output if valid else None,
            errors=errors,
            warnings=[],
            metrics={},
            evidence_summary=""
        )

    def _format_validation_errors(self, e: ValidationError) -> List[str]:
        formatted = []
        for error in e.errors():
            loc_str = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            err_type = error["type"]
            formatted.append(f"Field '{loc_str}': {msg} (type={err_type})")
        return formatted
