from typing import List, Optional
from pydantic import BaseModel, Field

class WebPageFetcherInput(BaseModel):
    """Pydantic input validation model for web_page_fetcher tool."""
    url: str = Field(
        ..., 
        pattern="^https?:\\/\\/.*",
        description="Target website URL."
    )

class WebPageFetcherOutput(BaseModel):
    """Pydantic output validation model for web_page_fetcher tool."""
    status: int = Field(..., description="HTTP status code returned by the target site.")
    content: Optional[str] = Field(None, description="Raw sanitized webpage HTML.")

class TechFootprintScannerInput(BaseModel):
    """Pydantic input validation model for tech_footprint_scanner tool."""
    url: str = Field(
        ..., 
        pattern="^https?:\\/\\/.*",
        description="Target website URL."
    )

class TechFootprintScannerOutput(BaseModel):
    """Pydantic output validation model for tech_footprint_scanner tool."""
    cms: str = Field(..., description="Identified Content Management System name.")
    load_time_seconds: float = Field(..., description="Measured load time of the domain.")
    has_booking_widget: Optional[bool] = Field(None, description="Check for booking scheduler widget existence.")

class SeoAuditorInput(BaseModel):
    """Pydantic input validation model for seo_auditor tool."""
    url: str = Field(
        ..., 
        pattern="^https?:\\/\\/.*",
        description="Target website URL."
    )

class SeoData(BaseModel):
    """SEO audit metrics payload."""
    meta_title: Optional[str] = Field(None, description="HTML head title tag value.")
    meta_description: Optional[str] = Field(None, description="HTML head meta description tag value.")
    h1_elements: List[str] = Field(..., description="Extracted HTML H1 element text values.")
    has_schema_markup: bool = Field(..., description="Check for Structured schema markup blocks.")

class SeoAuditorOutput(BaseModel):
    """Pydantic output validation model for seo_auditor tool."""
    seo_data: SeoData = Field(..., description="Parsed SEO metadata object.")
