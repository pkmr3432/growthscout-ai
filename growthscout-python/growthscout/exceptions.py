# growthscout-python/growthscout/exceptions.py
"""
Exceptions hierarchy for the GrowthScout AI Python SDK.
"""

class GrowthScoutError(Exception):
    """Base exception class for all SDK errors."""
    pass


class GrowthScoutNetworkError(GrowthScoutError):
    """Raised when request timeouts or host is unreachable."""
    pass


class GrowthScoutAuthenticationError(GrowthScoutError):
    """Raised on HTTP 401 Unauthorized errors."""
    pass


class GrowthScoutValidationError(GrowthScoutError):
    """Raised on HTTP 400 or HTTP 422 validation errors."""
    pass


class GrowthScoutRateLimitError(GrowthScoutError):
    """Raised on HTTP 429 rate limit exceeded. Exposes retry_after duration."""
    def __init__(self, message: str, retry_after: float = 1.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class GrowthScoutLockConflictError(GrowthScoutError):
    """Raised on HTTP 409 Conflict errors (session executing/locked)."""
    pass


class GrowthScoutPayloadTooLargeError(GrowthScoutError):
    """Raised on HTTP 413 body size limit violations."""
    pass
