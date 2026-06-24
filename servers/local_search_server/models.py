from typing import List, Optional
from pydantic import BaseModel, Field

class LocalSearchInput(BaseModel):
    """Pydantic input validation model for local_business_search tool."""
    query: str = Field(
        ..., 
        min_length=5, 
        max_length=256, 
        pattern="^[a-zA-Z0-9\\s\\,\\-\\.]+$",
        description="Search query containing niche and city coordinates."
    )
    page_token: Optional[str] = Field(
        None, 
        description="Google Places API pagination token."
    )

class BusinessResult(BaseModel):
    """Factual business result returned for a single lead."""
    name: str
    formatted_address: str
    website: Optional[str] = None
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None

class LocalSearchOutput(BaseModel):
    """Standardized output payload response."""
    results: List[BusinessResult]
