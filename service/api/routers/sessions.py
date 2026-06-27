# service/api/routers/sessions.py
"""
FastAPI router mapping HTTP request actions to ExecutionService.
"""

import asyncio
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Request
from service.api.schemas.v1.session import (
    SessionCreateRequest,
    SessionResponse,
    FeedbackSubmitRequest
)
from service.api.schemas.v1.error import StandardErrorResponse
from service.api.dependencies import verify_api_key, get_execution_service
from service.application.execution_service import ExecutionService

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions Operations"],
    dependencies=[Depends(verify_api_key)]
)

@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        403: {"model": StandardErrorResponse, "description": "Forbidden"}
    }
)
async def create_session(
    payload: SessionCreateRequest,
    service: ExecutionService = Depends(get_execution_service)
):
    """
    Initializes a new session and validates the initial lifecycle.
    """
    doc = await service.create_session(
        niche=payload.niche,
        location=payload.location,
        max_leads=payload.max_leads
    )
    return SessionResponse(**doc)

@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found"}
    }
)
async def get_session(
    session_id: str,
    service: ExecutionService = Depends(get_execution_service)
):
    """
    Retrieves current checkpoint state details for a specific session ID.
    """
    doc = await service.get_session(session_id)
    return SessionResponse(**doc)

@router.post(
    "/{session_id}/run",
    response_model=SessionResponse,
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        409: {"model": StandardErrorResponse, "description": "Conflict (Session Locked)"}
    }
)
async def run_session(
    session_id: str,
    request: Request,
    service: ExecutionService = Depends(get_execution_service)
):
    """
    Triggers execution loop run for a session ID. Checks locks and schedules background tasks.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    doc = await service.run_session(session_id, request_id, correlation_id)
    return SessionResponse(**doc)

@router.post(
    "/{session_id}/feedback",
    response_model=SessionResponse,
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found"}
    }
)
async def submit_feedback(
    session_id: str,
    payload: FeedbackSubmitRequest,
    request: Request,
    service: ExecutionService = Depends(get_execution_service)
):
    """
    Submits feedback to resume workflow from a human review gate.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    correlation_id = getattr(request.state, "correlation_id", "unknown")
    doc = await service.submit_feedback(
        session_id=session_id,
        approved=payload.approved,
        feedback_notes=payload.feedback_notes,
        adjusted_data=payload.adjusted_data,
        request_id=request_id,
        correlation_id=correlation_id
    )
    return SessionResponse(**doc)

@router.post(
    "/{session_id}/cancel",
    response_model=SessionResponse,
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized"}
    }
)
async def cancel_session(
    session_id: str,
    service: ExecutionService = Depends(get_execution_service)
):
    """
    Cooperatively cancels actively running background tasks for the session.
    """
    doc = await service.cancel_session(session_id)
    return SessionResponse(**doc)

@router.get(
    "/{session_id}/stream",
    responses={
        401: {"model": StandardErrorResponse, "description": "Unauthorized"},
        404: {"model": StandardErrorResponse, "description": "Session Not Found"}
    }
)
async def stream_session(
    session_id: str,
    request: Request,
    service: ExecutionService = Depends(get_execution_service)
):
    """
    Establishes a Server-Sent Events (SSE) channel streaming real-time
    execution events for the specified session.

    Supports reconnection via the Last-Event-ID header — missed events
    are replayed from the bounded replay buffer before live streaming resumes.
    """
    from fastapi.responses import StreamingResponse
    from service.infrastructure.registry import registry

    # Validate session exists before opening stream
    await service.get_session(session_id)

    # Parse Last-Event-ID for replay support
    last_event_id_raw = request.headers.get("Last-Event-ID")
    last_event_id: Optional[int] = None
    if last_event_id_raw is not None:
        try:
            last_event_id = int(last_event_id_raw)
        except (ValueError, TypeError):
            last_event_id = None

    publisher = registry.event_publisher

    async def sse_generator():
        """Async generator yielding SSE-formatted event strings."""
        try:
            async for envelope in publisher.subscribe(session_id, last_event_id=last_event_id):
                yield envelope.to_sse_format()
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )
