# service/api/routers/metrics.py
"""
Prometheus-compatible metrics endpoint exposing application performance counters.

Provides internal observability data in a format compatible with Prometheus scrapers,
including request counts, active sessions, streaming subscriber counts, and scheduler state.
"""

import time
import logging
from fastapi import APIRouter, Response
from service.infrastructure.registry import registry

logger = logging.getLogger("growthscout.metrics")

router = APIRouter(tags=["Metrics & Observability"])

# Application-level counters
_request_counter: int = 0
_error_counter: int = 0
_start_time: float = time.monotonic()


def increment_request_counter() -> None:
    """Increment the global request counter (called from middleware)."""
    global _request_counter
    _request_counter += 1


def increment_error_counter() -> None:
    """Increment the global error counter (called from error handlers)."""
    global _error_counter
    _error_counter += 1


@router.get(
    "/metrics",
    response_class=Response,
    operation_id="prometheusMetrics",
    summary="Expose Prometheus metrics",
    description="Exposes application metrics in Prometheus text exposition format including uptime, request count, active runs, locks, and SSE subscribers."
)
async def prometheus_metrics():
    """
    Exposes application metrics in Prometheus text exposition format.

    Metrics exposed:
        - growthscout_uptime_seconds: Time since application start.
        - growthscout_requests_total: Total HTTP requests handled.
        - growthscout_errors_total: Total error responses returned.
        - growthscout_active_tasks: Currently running background tasks.
        - growthscout_active_locks: Currently held session locks.
        - growthscout_checkpoint_dir: Configured checkpoint storage directory.
    """
    uptime = time.monotonic() - _start_time

    # Gather scheduler metrics
    scheduler = registry.task_scheduler
    active_tasks = len([t for t in scheduler._tasks.values() if not t.done()])
    total_tasks_tracked = len(scheduler._tasks)

    # Gather lock manager metrics
    lock_mgr = registry.lock_manager
    active_locks = 0
    for lock in lock_mgr._locks.values():
        if lock.locked():
            active_locks += 1

    # Gather publisher metrics
    publisher = registry.event_publisher
    total_subscribers = 0
    total_events_published = 0
    if hasattr(publisher, '_subscribers'):
        for session_queues in publisher._subscribers.values():
            total_subscribers += len(session_queues)
    if hasattr(publisher, '_event_counters'):
        total_events_published = sum(publisher._event_counters.values())

    lines = [
        "# HELP growthscout_uptime_seconds Time since application start in seconds.",
        "# TYPE growthscout_uptime_seconds gauge",
        f"growthscout_uptime_seconds {uptime:.2f}",
        "",
        "# HELP growthscout_requests_total Total HTTP requests handled.",
        "# TYPE growthscout_requests_total counter",
        f"growthscout_requests_total {_request_counter}",
        "",
        "# HELP growthscout_errors_total Total error responses returned.",
        "# TYPE growthscout_errors_total counter",
        f"growthscout_errors_total {_error_counter}",
        "",
        "# HELP growthscout_active_tasks Currently running background workflow tasks.",
        "# TYPE growthscout_active_tasks gauge",
        f"growthscout_active_tasks {active_tasks}",
        "",
        "# HELP growthscout_tracked_tasks_total Total tasks tracked by scheduler (including completed).",
        "# TYPE growthscout_tracked_tasks_total gauge",
        f"growthscout_tracked_tasks_total {total_tasks_tracked}",
        "",
        "# HELP growthscout_active_locks Currently held session locks.",
        "# TYPE growthscout_active_locks gauge",
        f"growthscout_active_locks {active_locks}",
        "",
        "# HELP growthscout_sse_subscribers Active SSE streaming subscribers.",
        "# TYPE growthscout_sse_subscribers gauge",
        f"growthscout_sse_subscribers {total_subscribers}",
        "",
        "# HELP growthscout_events_published_total Total events published to SSE subscribers.",
        "# TYPE growthscout_events_published_total counter",
        f"growthscout_events_published_total {total_events_published}",
        "",
    ]

    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )
