# service/infrastructure/logging.py
"""
Structured JSON logging for the GrowthScout AI service layer.

Provides a custom JSON formatter that includes standard context fields
(timestamp, request_id, correlation_id, session_id, workflow_id, component, level)
in every log record.

Usage:
    Call `configure_logging(settings)` during application startup.
"""

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Optional


class StructuredJSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects with structured fields.

    Fields included:
        - timestamp: ISO-8601 UTC timestamp
        - level: Log level name
        - component: Logger name (e.g., 'growthscout.execution_service')
        - message: Log message text
        - request_id: Request trace ID (from extra or context)
        - correlation_id: Correlation ID (from extra or context)
        - session_id: Session ID (from extra or context)
        - workflow_id: Workflow ID (from extra or context)
        - module: Python module name
        - function: Function name
        - line: Line number
        - exception: Exception info (if present)
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
            "correlation_id": getattr(record, "correlation_id", None),
            "session_id": getattr(record, "session_id", None),
            "workflow_id": getattr(record, "workflow_id", None),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[1] is not None:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # Remove None values for cleaner output
        log_entry = {k: v for k, v in log_entry.items() if v is not None}

        return json.dumps(log_entry, default=str)


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable log format for local development.
    """
    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    def __init__(self):
        super().__init__(fmt=self.FORMAT, datefmt="%Y-%m-%d %H:%M:%S")


class RequestContextFilter(logging.Filter):
    """
    Logging filter that attaches request context fields to every log record.
    Falls back to empty values when no request context is available.
    """
    _context: dict = {}

    @classmethod
    def set_context(cls, **kwargs) -> None:
        """Set the current request context (called from middleware)."""
        cls._context = kwargs

    @classmethod
    def clear_context(cls) -> None:
        """Clear the current request context."""
        cls._context = {}

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = self._context.get("request_id")
        record.correlation_id = self._context.get("correlation_id")
        record.session_id = self._context.get("session_id")
        record.workflow_id = self._context.get("workflow_id")
        return True


def configure_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    service_name: str = "growthscout-service"
) -> None:
    """
    Configures the root logger with structured JSON or human-readable formatting.

    Args:
        log_level: Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: 'json' for structured JSON output, 'text' for human-readable.
        service_name: Service name included in structured logs.
    """
    # Resolve numeric level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)

    # Choose formatter
    if log_format == "json":
        formatter = StructuredJSONFormatter()
    else:
        formatter = HumanReadableFormatter()

    handler.setFormatter(formatter)

    # Add context filter
    context_filter = RequestContextFilter()
    handler.addFilter(context_filter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicates
    for existing_handler in root_logger.handlers[:]:
        root_logger.removeHandler(existing_handler)

    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy in ["uvicorn.access", "uvicorn.error", "httpcore", "httpx", "asyncio"]:
        logging.getLogger(noisy).setLevel(max(numeric_level, logging.WARNING))

    logging.getLogger("growthscout").info(
        f"Logging configured: level={log_level}, format={log_format}, service={service_name}"
    )
