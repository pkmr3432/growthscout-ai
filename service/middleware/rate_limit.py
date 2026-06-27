# service/middleware/rate_limit.py
"""
Token bucket rate limiter middleware for the GrowthScout AI service layer.

Enforces per-client request rate limits using an in-memory token bucket algorithm.
Clients are identified by their X-API-Key header value or IP address.
"""

import time
import asyncio
import logging
from collections import defaultdict
from typing import Dict, Tuple, Optional

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from datetime import datetime, timezone

logger = logging.getLogger("growthscout.rate_limit")


class TokenBucket:
    """
    Thread-safe token bucket implementation for rate limiting.

    Parameters:
        capacity: Maximum number of tokens (burst capacity).
        refill_rate: Tokens added per second.
    """
    def __init__(self, capacity: int, refill_rate: float) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """
        Attempts to consume one token. Returns True if successful, False if rate-limited.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False

    @property
    def retry_after_seconds(self) -> float:
        """
        Calculates seconds until the next token is available.
        """
        if self.tokens >= 1.0:
            return 0.0
        return (1.0 - self.tokens) / self.refill_rate


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Starlette-compatible middleware enforcing per-client token bucket rate limits.

    Configuration:
        requests_per_second: Maximum sustained request rate per client.
        burst_capacity: Maximum burst size before throttling begins.
        exclude_paths: Set of path prefixes excluded from rate limiting (e.g., /health, /metrics).
    """
    def __init__(
        self,
        app,
        requests_per_second: float = 10.0,
        burst_capacity: int = 20,
        exclude_paths: Optional[set] = None
    ) -> None:
        super().__init__(app)
        self.requests_per_second = requests_per_second
        self.burst_capacity = burst_capacity
        self.exclude_paths = exclude_paths or {"/health", "/ready", "/startup-check", "/metrics", "/openapi.json", "/docs", "/redoc"}
        self._buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    def _get_client_id(self, request: Request) -> str:
        """
        Resolves client identity from X-API-Key header or fallback to client IP.
        """
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key}"
        # Fallback to client host IP
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Intercepts incoming requests and applies rate limiting before forwarding.
        """
        # Skip rate limiting for excluded paths
        for prefix in self.exclude_paths:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        client_id = self._get_client_id(request)

        async with self._lock:
            if client_id not in self._buckets:
                self._buckets[client_id] = TokenBucket(
                    capacity=self.burst_capacity,
                    refill_rate=self.requests_per_second
                )
            bucket = self._buckets[client_id]

        if not bucket.consume():
            retry_after = bucket.retry_after_seconds
            logger.warning(f"Rate limit exceeded for client {client_id}")

            request_id = getattr(request.state, "request_id", "unknown") if hasattr(request, "state") else "unknown"
            correlation_id = getattr(request.state, "correlation_id", "unknown") if hasattr(request, "state") else "unknown"

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many requests. Retry after {retry_after:.1f} seconds.",
                        "request_id": request_id,
                        "correlation_id": correlation_id,
                        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "retryable": True,
                        "details": {
                            "retry_after_seconds": round(retry_after, 2),
                            "limit": self.requests_per_second,
                            "burst_capacity": self.burst_capacity
                        }
                    }
                },
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Limit": str(self.burst_capacity),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + int(retry_after) + 1)
                }
            )

        # Forward request and inject rate limit response headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.burst_capacity)
        remaining = max(0, int(bucket.tokens))
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + int(self.burst_capacity / self.requests_per_second))
        return response
