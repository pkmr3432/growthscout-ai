# agents/orchestrator_agent/run_budget.py
"""
WorkflowRunBudget — Centralized runtime budget manager for GrowthScout AI.
Tracks external resource usage (Gemini API calls, Maps API lookups, scraper crawled pages)
and execution limits.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

class WorkflowRunBudget(BaseModel):
    # Resource counters
    gemini_requests: int = Field(default=0, description="Count of Gemini model calls.")
    maps_requests: int = Field(default=0, description="Count of Google Maps API calls.")
    pages_crawled: int = Field(default=0, description="Count of crawled/scraped pages.")
    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Time when the workflow run started."
    )
    estimated_cost: float = Field(default=0.0, description="Calculated cost of the workflow run.")

    # Threshold limits
    max_gemini_requests: int = 20
    max_maps_requests: int = 15
    max_pages_crawled: int = 10
    max_elapsed_seconds: float = 600.0
    max_cost_limit: float = 5.00

    # Pricing config (cost per action)
    gemini_cost_per_request: float = 0.002
    maps_cost_per_request: float = 0.005
    pages_cost_per_request: float = 0.001

    model_config = {
        "arbitrary_types_allowed": True
    }

    def can_continue(self, operation: str) -> bool:
        """
        Check if an operation can proceed without exceeding budget boundaries.
        
        Args:
            operation: One of "gemini", "maps", "scraper"
        """
        elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        if elapsed > self.max_elapsed_seconds:
            return False

        if self.estimated_cost >= self.max_cost_limit:
            return False

        if operation == "gemini":
            if self.gemini_requests >= self.max_gemini_requests:
                return False
            if self.estimated_cost + self.gemini_cost_per_request > self.max_cost_limit:
                return False
        elif operation == "maps":
            if self.maps_requests >= self.max_maps_requests:
                return False
            if self.estimated_cost + self.maps_cost_per_request > self.max_cost_limit:
                return False
        elif operation == "scraper":
            if self.pages_crawled >= self.max_pages_crawled:
                return False
            if self.estimated_cost + self.pages_cost_per_request > self.max_cost_limit:
                return False
        else:
            # Unknown operation
            pass

        return True

    def record_operation(self, operation: str, count: int = 1) -> None:
        """Record resource usage and update the estimated cost."""
        if operation == "gemini":
            self.gemini_requests += count
            self.estimated_cost += self.gemini_cost_per_request * count
        elif operation == "maps":
            self.maps_requests += count
            self.estimated_cost += self.maps_cost_per_request * count
        elif operation == "scraper":
            self.pages_crawled += count
            self.estimated_cost += self.pages_cost_per_request * count
