import json
from typing import Any, Dict
from pydantic import BaseModel

def serialize_model(model: BaseModel) -> str:
    """Serializes a Pydantic model into a standardized JSON string format."""
    return model.model_dump_json()

def deserialize_model(model_class: Any, json_str: str) -> Any:
    """Deserializes a JSON string into the specified Pydantic model class."""
    return model_class.model_validate_json(json_str)
