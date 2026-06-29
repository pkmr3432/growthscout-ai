# growthscout-python/growthscout/client.py
"""
Synchronous and Asynchronous core client wrapper for the GrowthScout AI Python SDK.
"""

import asyncio
import random
import time
import httpx
from typing import Dict, Any, List, Optional

from growthscout.exceptions import (
    GrowthScoutError, GrowthScoutNetworkError, GrowthScoutAuthenticationError,
    GrowthScoutValidationError, GrowthScoutRateLimitError,
    GrowthScoutLockConflictError, GrowthScoutPayloadTooLargeError
)
from growthscout.models import SessionResponse, SessionCreateRequest, FeedbackSubmitRequest
from growthscout.streaming import EventStream


class GrowthScout:
    """
    Core SDK wrapper client coordinating configuration, authentication, retries,
    exceptions mapping, and session/stream endpoint resources.
    """
    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3
    ) -> None:
        if not api_key or not isinstance(api_key, str):
            raise GrowthScoutAuthenticationError("Invalid API key. Must be a non-empty string.")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.sessions = SessionsResource(self)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _request(
        self,
        method: str,
        path: str,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes HTTP requests with transient retry middleware, exponential backoff,
        jitter, and standard exception mapping checks.
        """
        url = f"{self.base_url}{path}"
        headers = self._get_headers()
        attempt = 0

        while True:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, json=json_data, params=params, headers=headers)
                    
                if response.status_code in [200, 201]:
                    return response.json()

                # Process HTTP status code conversions
                self._handle_status_error(response.status_code, response.text)

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise GrowthScoutNetworkError(f"Network error after {attempt} attempts: {str(e)}")
                
                # Exponential backoff with jitter
                sleep_time = min(10.0, 1.0 * (2 ** attempt)) + random.uniform(0.1, 0.5)
                await asyncio.sleep(sleep_time)

    def _handle_status_error(self, status_code: int, response_text: str):
        """Converts error statuses to specific SDK exceptions."""
        try:
            error_json = httpx.Response(status_code, content=response_text.encode()).json()
            message = error_json.get("error", {}).get("message", "API Error occurred.")
        except Exception:
            message = f"HTTP Error status {status_code}: {response_text}"

        if status_code == 400:
            raise GrowthScoutValidationError(message)
        elif status_code == 401:
            raise GrowthScoutAuthenticationError(message)
        elif status_code == 403:
            raise GrowthScoutAuthenticationError(f"Forbidden: {message}")
        elif status_code == 404:
            raise GrowthScoutValidationError(f"Not Found: {message}")
        elif status_code == 409:
            raise GrowthScoutLockConflictError(message)
        elif status_code == 413:
            raise GrowthScoutPayloadTooLargeError(message)
        elif status_code == 429:
            # Handle rate limit retry after calculation
            raise GrowthScoutRateLimitError(message, retry_after=1.0)
        else:
            raise GrowthScoutError(f"HTTP {status_code}: {message}")


class SessionsResource:
    """Namespace for session operations inside the Python SDK client."""
    def __init__(self, client: GrowthScout) -> None:
        self.client = client

    async def create(self, niche: str, location: str, max_leads: int = 5) -> SessionResponse:
        """Initializes a new session."""
        req = SessionCreateRequest(niche=niche, location=location, max_leads=max_leads)
        doc = await self.client._request("POST", "/api/v1/sessions", json_data=req.model_dump())
        return SessionResponse(**doc)

    async def get(self, session_id: str) -> SessionResponse:
        """Retrieves session status."""
        doc = await self.client._request("GET", f"/api/v1/sessions/{session_id}")
        return SessionResponse(**doc)

    async def run(self, session_id: str) -> SessionResponse:
        """Triggers workflow execution run."""
        doc = await self.client._request("POST", f"/api/v1/sessions/{session_id}/run")
        return SessionResponse(**doc)

    async def submit_feedback(
        self,
        session_id: str,
        approved: bool,
        feedback_notes: Optional[str] = None,
        adjusted_data: Optional[Dict[str, Any]] = None
    ) -> SessionResponse:
        """Submits human validation feedback."""
        req = FeedbackSubmitRequest(approved=approved, feedback_notes=feedback_notes, adjusted_data=adjusted_data)
        doc = await self.client._request("POST", f"/api/v1/sessions/{session_id}/feedback", json_data=req.model_dump())
        return SessionResponse(**doc)

    async def cancel(self, session_id: str) -> SessionResponse:
        """Cancels active workflow execution."""
        doc = await self.client._request("POST", f"/api/v1/sessions/{session_id}/cancel")
        return SessionResponse(**doc)

    def stream(self, session_id: str) -> EventStream:
        """Exposes standard event stream generator listener."""
        return EventStream(self.client, session_id)

    async def list_sessions(self, limit: int = 20, offset: int = 0) -> List[SessionResponse]:
        """Pagination helper returning list of sessions."""
        params = {"limit": limit, "offset": offset}
        # In this endpoint layout, list is handled under GET prefix /sessions
        docs = await self.client._request("GET", "/api/v1/sessions", params=params)
        # Note: If GET /sessions directly returns list or pagination envelope:
        if isinstance(docs, list):
            return [SessionResponse(**d) for d in docs]
        elif isinstance(docs, dict) and "sessions" in docs:
            return [SessionResponse(**d) for d in docs["sessions"]]
        return []
