# service/middleware/security.py
"""
Security headers middleware for the GrowthScout AI service layer.

Injects standard security response headers to prevent common web vulnerabilities:
- XSS (X-Content-Type-Options, X-XSS-Protection)
- Clickjacking (X-Frame-Options)
- Transport security (Strict-Transport-Security)
- Content sniffing (X-Content-Type-Options)
- Referrer leakage (Referrer-Policy)
- Permission restrictions (Permissions-Policy)
"""

import logging
from typing import Optional, List

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger("growthscout.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Starlette-compatible middleware injecting security response headers.

    Configuration:
        enable_hsts: Enable HTTP Strict Transport Security header (production only).
        hsts_max_age: Max age for HSTS in seconds (default: 1 year).
        frame_options: X-Frame-Options value (DENY or SAMEORIGIN).
        content_type_options: X-Content-Type-Options value.
        referrer_policy: Referrer-Policy header value.
    """

    def __init__(
        self,
        app,
        enable_hsts: bool = False,
        hsts_max_age: int = 31536000,
        frame_options: str = "DENY",
        content_type_options: str = "nosniff",
        referrer_policy: str = "strict-origin-when-cross-origin",
        permissions_policy: str = "camera=(), microphone=(), geolocation=()"
    ) -> None:
        super().__init__(app)
        self.enable_hsts = enable_hsts
        self.hsts_max_age = hsts_max_age
        self.frame_options = frame_options
        self.content_type_options = content_type_options
        self.referrer_policy = referrer_policy
        self.permissions_policy = permissions_policy

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Forwards request and injects security headers into the response.
        """
        response = await call_next(request)

        # Core security headers
        response.headers["X-Content-Type-Options"] = self.content_type_options
        response.headers["X-Frame-Options"] = self.frame_options
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = self.referrer_policy
        response.headers["Permissions-Policy"] = self.permissions_policy
        response.headers["Cache-Control"] = response.headers.get(
            "Cache-Control", "no-store, no-cache, must-revalidate"
        )

        # HSTS header (only in production with TLS termination)
        if self.enable_hsts:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={self.hsts_max_age}; includeSubDomains; preload"
            )

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware enforcing maximum request body size limits.
    Returns HTTP 413 Payload Too Large for oversized requests.
    """

    def __init__(self, app, max_size_bytes: int = 10_485_760) -> None:
        super().__init__(app)
        self.max_size_bytes = max_size_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Checks Content-Length header and rejects oversized requests.
        """
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    from fastapi.responses import JSONResponse
                    from datetime import datetime, timezone
                    logger.warning(
                        f"Request rejected: Content-Length {size} exceeds limit {self.max_size_bytes}"
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds maximum allowed size of {self.max_size_bytes} bytes.",
                                "request_id": "unknown",
                                "correlation_id": "unknown",
                                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                "retryable": False,
                                "details": {
                                    "max_size_bytes": self.max_size_bytes,
                                    "received_bytes": size
                                }
                            }
                        }
                    )
            except (ValueError, TypeError):
                pass

        return await call_next(request)
